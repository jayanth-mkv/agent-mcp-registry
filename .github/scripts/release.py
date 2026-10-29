"""Validate independent MCP releases and the exact distributions being uploaded."""

from __future__ import annotations

import argparse
import configparser
from email.parser import BytesParser
import json
import os
from pathlib import Path
import re
import subprocess
import tarfile
import tempfile
import tomllib
import zipfile

PACKAGES = ("mcp-files", "mcp-email-validator")
DISTRIBUTIONS = {
    "mcp-files": "agent-mcp-registry-files",
    "mcp-email-validator": "mcp-email-validator",
}
ENVIRONMENTS = {"mcp-files": "pypi-files", "mcp-email-validator": "pypi"}
ROOT = Path(__file__).resolve().parents[2]
VERSION_PATTERN = r"(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)(?:(?:a|b|rc)\d+)?"


def project(package: str, root: Path = ROOT) -> dict:
    if package not in PACKAGES:
        raise ValueError("Choose mcp-files or mcp-email-validator")
    metadata = tomllib.loads((root / package / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    if metadata["name"] != DISTRIBUTIONS[package]:
        raise ValueError("Project name does not match the package's registered distribution")
    if not re.fullmatch(VERSION_PATTERN, metadata["version"]):
        raise ValueError("Use a three-part version, optionally followed by a, b, or rc and a number")
    if package not in metadata.get("scripts", {}):
        raise ValueError("Package must provide its named console command")
    return metadata


def select(event: str, ref: str, requested: str = "", root: Path = ROOT) -> dict[str, str]:
    if event == "push":
        match = re.fullmatch(rf"refs/tags/({'|'.join(PACKAGES)})-v({VERSION_PATTERN})", ref)
        if not match:
            raise ValueError("Publishing requires a package-specific version tag")
        package, version = match.groups()
        if project(package, root)["version"] != version:
            raise ValueError("Release tag version does not match pyproject.toml")
        publish = "true"
    elif event == "workflow_dispatch":
        package = requested
        version = project(package, root)["version"]
        publish = "false"
    else:
        raise ValueError("Unsupported release event")
    return {
        "package": package, "distribution": DISTRIBUTIONS[package],
        "environment": ENVIRONMENTS[package], "version": version, "publish": publish,
    }


def validate_metadata(content: bytes, expected: dict) -> None:
    metadata = BytesParser().parsebytes(content)
    normalize = lambda name: re.sub(r"[-_.]+", "-", name).lower()
    if normalize(metadata.get("Name", "")) != normalize(expected["name"]):
        raise ValueError("Distribution contains a different package")
    if metadata.get("Version") != expected["version"]:
        raise ValueError("Distribution contains a different version")
    if metadata.get("Requires-Python") != expected["requires-python"]:
        raise ValueError("Distribution Python requirement does not match the project")


def validate_paths(names: list[str]) -> None:
    for name in names:
        parts = Path(name).parts
        if any(part in {".venv", "node_modules", "__pycache__", ".env"} or part.startswith(".env.") for part in parts):
            raise ValueError("Distribution includes local environment or cache files")
    if not any(Path(name).name == "LICENSE" for name in names):
        raise ValueError("Distribution must include its license")


def check_distributions(package: str, directory: Path, root: Path = ROOT) -> Path:
    expected = project(package, root)
    # uv creates a .gitignore in its output directory; it is not a distribution.
    files = [path for path in directory.iterdir() if path.name != ".gitignore"]
    wheels = [path for path in files if path.name.endswith(".whl")]
    sources = [path for path in files if path.name.endswith(".tar.gz")]
    if len(files) != 2 or len(wheels) != 1 or len(sources) != 1:
        raise ValueError("Expected exactly one wheel and one source distribution")
    wheel = wheels[0]
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        validate_paths(names)
        metadata = [name for name in names if name.endswith(".dist-info/METADATA")]
        entrypoints = [name for name in names if name.endswith(".dist-info/entry_points.txt")]
        if len(metadata) != 1 or len(entrypoints) != 1:
            raise ValueError("Wheel metadata or console entry points are missing")
        validate_metadata(archive.read(metadata[0]), expected)
        parser = configparser.ConfigParser()
        parser.read_string(archive.read(entrypoints[0]).decode("utf-8"))
        if dict(parser["console_scripts"]) != expected["scripts"]:
            raise ValueError("Wheel console commands do not match the project")
    with tarfile.open(sources[0], "r:gz") as archive:
        names = archive.getnames()
        validate_paths(names)
        metadata = [member for member in archive.getmembers() if len(Path(member.name).parts) == 2 and member.name.endswith("/PKG-INFO")]
        if len(metadata) != 1:
            raise ValueError("Source distribution metadata is missing")
        stream = archive.extractfile(metadata[0])
        if stream is None:
            raise ValueError("Source distribution metadata is unreadable")
        validate_metadata(stream.read(), expected)
    return wheel.resolve()


def output(values: dict[str, str]) -> None:
    print(json.dumps(values))
    if destination := os.environ.get("GITHUB_OUTPUT"):
        with open(destination, "a", encoding="utf-8") as stream:
            for key, value in values.items():
                stream.write(f"{key}={value}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    select_parser = commands.add_parser("select")
    select_parser.add_argument("--event", required=True)
    select_parser.add_argument("--ref", required=True)
    select_parser.add_argument("--package", default="")
    inspect_parser = commands.add_parser("inspect")
    inspect_parser.add_argument("--package", required=True, choices=PACKAGES)
    check_parser = commands.add_parser("check")
    check_parser.add_argument("--package", required=True, choices=PACKAGES)
    check_parser.add_argument("--dist", required=True, type=Path)
    check_parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    if args.command == "select":
        output(select(args.event, args.ref, args.package))
    elif args.command == "inspect":
        metadata = project(args.package)
        output({"package": args.package, "distribution": metadata["name"], "version": metadata["version"]})
    else:
        wheel = check_distributions(args.package, args.dist)
        if args.smoke:
            with tempfile.TemporaryDirectory(prefix="mcp-wheel-") as temporary:
                subprocess.run([
                    "uv", "tool", "run", "--isolated", "--python", "3.13",
                    "--from", str(wheel), args.package, "--help",
                ], cwd=temporary, check=True)
        print(f"Validated {args.package}: wheel, source distribution, metadata, and entry points")


if __name__ == "__main__":
    main()

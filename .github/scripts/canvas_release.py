"""Build small, checksummed native Canvas MCP release artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tarfile
import tomllib
import zipfile

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "mcp-canvas-lms"
TARGETS = (
    "x86_64-unknown-linux-gnu", "aarch64-unknown-linux-gnu",
    "x86_64-pc-windows-msvc", "aarch64-apple-darwin", "x86_64-apple-darwin",
)


def version():
    metadata = tomllib.loads((PACKAGE / "Cargo.toml").read_text(encoding="utf-8"))["package"]
    if metadata["name"] != "mcp-canvas-lms" or not re.fullmatch(r"\d+\.\d+\.\d+", metadata["version"]):
        raise ValueError("Expected the mcp-canvas-lms package and a three-part release version")
    return metadata["version"]


def target(event, ref):
    current = version()
    publish = event == "push" and ref.startswith("refs/tags/")
    if publish and ref != f"refs/tags/mcp-canvas-lms-v{current}":
        raise ValueError("Canvas release tag does not match Cargo.toml")
    if event not in {"push", "pull_request", "workflow_dispatch"}:
        raise ValueError("Unsupported release event")
    return {"version": current, "publish": str(publish).lower()}


def package(binary, architecture, output):
    current = version()
    expected = f"mcp-canvas-lms {current}"
    result = subprocess.run([str(binary.resolve()), "--version"], capture_output=True, text=True, check=True)
    if result.stdout.strip() != expected:
        raise ValueError("Binary version does not match Cargo.toml")
    output.mkdir(parents=True, exist_ok=True)
    base = f"mcp-canvas-lms-v{current}-{architecture}"
    windows = architecture.endswith("windows-msvc")
    filename = "mcp-canvas-lms.exe" if windows else "mcp-canvas-lms"
    members = [(binary, filename), (PACKAGE / "LICENSE", "LICENSE"), (PACKAGE / "README.md", "README.md")]
    path = output / (base + (".zip" if windows else ".tar.gz"))
    if windows:
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for source, name in members:
                archive.write(source, name)
    else:
        with tarfile.open(path, "w:gz", compresslevel=9) as archive:
            for source, name in members:
                archive.add(source, arcname=name, recursive=False)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    path.with_name(path.name + ".sha256").write_text(f"{digest}  {path.name}\n", encoding="utf-8")
    print(json.dumps({"archive": str(path), "binary_bytes": binary.stat().st_size,
                      "download_bytes": path.stat().st_size, "sha256": digest}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate")
    validate.add_argument("--event", required=True)
    validate.add_argument("--ref", required=True)
    pack = commands.add_parser("package")
    pack.add_argument("--binary", required=True, type=Path)
    pack.add_argument("--target", required=True, choices=TARGETS)
    pack.add_argument("--out", required=True, type=Path)
    compare = commands.add_parser("compare")
    compare.add_argument("--tested", required=True, type=Path)
    compare.add_argument("--candidate", required=True, type=Path)
    args = parser.parse_args()
    if args.command == "validate":
        values = target(args.event, args.ref)
        print(json.dumps(values))
        if destination := os.environ.get("GITHUB_OUTPUT"):
            with open(destination, "a", encoding="utf-8") as stream:
                stream.writelines(f"{key}={value}\n" for key, value in values.items())
    elif args.command == "package":
        package(args.binary, args.target, args.out)
    else:
        if hashlib.sha256(args.tested.read_bytes()).digest() != hashlib.sha256(args.candidate.read_bytes()).digest():
            raise ValueError("Publish candidate differs from the crate verified in the build job")
        print("Crate matches the tested distribution.")


if __name__ == "__main__":
    main()

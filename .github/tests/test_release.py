"""Reject wrong-package releases, mismatched tags, and contaminated artifacts."""

import io
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import release


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        for package in release.PACKAGES:
            folder = self.root / package
            folder.mkdir()
            (folder / "pyproject.toml").write_text(
                f'[project]\nname = "{release.DISTRIBUTIONS[package]}"\nversion = "0.2.0"\nrequires-python = ">=3.13"\n'
                f'[project.scripts]\n{package} = "server.cli:main"\n', encoding="utf-8",
            )

    def test_independent_release_tags(self):
        for package in release.PACKAGES:
            with self.subTest(package=package):
                target = release.select("push", f"refs/tags/{package}-v0.2.0", root=self.root)
                self.assertEqual(target, {
                    "package": package, "distribution": release.DISTRIBUTIONS[package],
                    "environment": release.ENVIRONMENTS[package], "version": "0.2.0", "publish": "true",
                })

    def test_pending_publishers_have_distinct_environments(self):
        files = release.select("push", "refs/tags/mcp-files-v0.2.0", root=self.root)
        email = release.select("push", "refs/tags/mcp-email-validator-v0.2.0", root=self.root)
        self.assertEqual(files["environment"], "pypi-files")
        self.assertEqual(email["environment"], "pypi")
        self.assertNotEqual(files["environment"], email["environment"])

    def test_wrong_tag_version_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "does not match"):
            release.select("push", "refs/tags/mcp-files-v9.0.0", root=self.root)

    def test_branch_push_and_unscoped_tags_cannot_publish(self):
        for ref in ("refs/heads/main", "refs/tags/v0.2.0", "refs/tags/experimental-v0.2.0", "refs/tags/mcp-files-v0.2.0\n"):
            with self.subTest(ref=ref), self.assertRaises(ValueError):
                release.select("push", ref, root=self.root)

    def test_manual_run_never_publishes_even_on_a_tag(self):
        target = release.select("workflow_dispatch", "refs/tags/mcp-files-v0.2.0", "mcp-files", root=self.root)
        self.assertEqual(target["publish"], "false")

    def test_invalid_package_and_event_are_rejected(self):
        for name in ("../mcp-files", "mcp-files\npublish=true", "experimental", ""):
            with self.subTest(name=name), self.assertRaises(ValueError):
                release.select("workflow_dispatch", "refs/heads/main", name, self.root)
        with self.assertRaises(ValueError):
            release.select("pull_request", "refs/heads/main", "mcp-files", self.root)

    def artifacts(self, *, wheel_name="mcp-files-context", wheel_version="0.2.0", source_name="mcp-files-context", source_version="0.2.0", entry="server.cli:main", extra=None):
        directory = self.root / "dist"
        directory.mkdir()
        wheel = directory / "mcp_files_context-0.2.0-py3-none-any.whl"
        info = "mcp_files_context-0.2.0.dist-info"
        with zipfile.ZipFile(wheel, "w") as archive:
            archive.writestr(f"{info}/METADATA", f"Name: {wheel_name}\nVersion: {wheel_version}\nRequires-Python: >=3.13\n\n")
            archive.writestr(f"{info}/entry_points.txt", f"[console_scripts]\nmcp-files = {entry}\n")
            archive.writestr(f"{info}/licenses/LICENSE", "MIT")
            if extra:
                archive.writestr(extra, "local data")
        with tarfile.open(directory / "mcp_files_context-0.2.0.tar.gz", "w:gz") as archive:
            for name, content in {
                "mcp_files_context-0.2.0/PKG-INFO": f"Name: {source_name}\nVersion: {source_version}\nRequires-Python: >=3.13\n\n",
                "mcp_files_context-0.2.0/LICENSE": "MIT",
            }.items():
                data = content.encode()
                member = tarfile.TarInfo(name)
                member.size = len(data)
                archive.addfile(member, io.BytesIO(data))
        return directory, wheel

    def test_valid_artifacts(self):
        directory, wheel = self.artifacts()
        self.assertEqual(release.check_distributions("mcp-files", directory, self.root), wheel.resolve())

    def test_wrong_wheel_identity_is_rejected(self):
        directory, _ = self.artifacts(wheel_name="mcp-email-validator")
        with self.assertRaisesRegex(ValueError, "different package"):
            release.check_distributions("mcp-files", directory, self.root)

    def test_uv_output_gitignore_is_allowed(self):
        directory, wheel = self.artifacts()
        (directory / ".gitignore").write_text("*")
        self.assertEqual(release.check_distributions("mcp-files", directory, self.root), wheel.resolve())

    def test_wrong_wheel_version_is_rejected(self):
        directory, _ = self.artifacts(wheel_version="9.0.0")
        with self.assertRaisesRegex(ValueError, "different version"):
            release.check_distributions("mcp-files", directory, self.root)

    def test_wrong_source_identity_is_rejected(self):
        directory, _ = self.artifacts(source_name="mcp-email-validator")
        with self.assertRaisesRegex(ValueError, "different package"):
            release.check_distributions("mcp-files", directory, self.root)

    def test_wrong_console_command_is_rejected(self):
        directory, _ = self.artifacts(entry="other.cli:main")
        with self.assertRaisesRegex(ValueError, "console commands"):
            release.check_distributions("mcp-files", directory, self.root)

    def test_local_secrets_in_wheel_are_rejected(self):
        directory, _ = self.artifacts(extra="server/.env.production")
        with self.assertRaisesRegex(ValueError, "environment or cache"):
            release.check_distributions("mcp-files", directory, self.root)

    def test_unexpected_extra_distribution_is_rejected(self):
        directory, _ = self.artifacts()
        (directory / "unrelated.whl").write_bytes(b"unrelated")
        with self.assertRaisesRegex(ValueError, "exactly one"):
            release.check_distributions("mcp-files", directory, self.root)


if __name__ == "__main__":
    unittest.main()

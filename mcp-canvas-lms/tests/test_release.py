"""Publication guards for the independent Rust release workflow."""

import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

source = Path(__file__).resolve().parents[2] / ".github/scripts/canvas_release.py"
spec = importlib.util.spec_from_file_location("canvas_release", source)
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


class ReleaseTests(unittest.TestCase):
    @patch.object(release, "version", return_value="0.1.0")
    def test_matching_canvas_tag_can_publish(self, _):
        self.assertEqual(release.target("push", "refs/tags/mcp-canvas-lms-v0.1.0"),
                         {"version": "0.1.0", "publish": "true"})

    @patch.object(release, "version", return_value="0.1.0")
    def test_manual_runs_and_branch_pushes_cannot_publish(self, _):
        for event, ref in (("push", "refs/heads/main"), ("workflow_dispatch", "refs/tags/mcp-canvas-lms-v0.1.0"),
                           ("pull_request", "refs/pull/1/merge")):
            self.assertEqual(release.target(event, ref)["publish"], "false")

    @patch.object(release, "version", return_value="0.1.0")
    def test_other_package_and_mismatched_tags_are_rejected(self, _):
        for ref in ("refs/tags/mcp-files-v0.1.0", "refs/tags/mcp-canvas-lms-v0.2.0", "refs/tags/mcp-canvas-lms-v0.1.0\n"):
            with self.subTest(ref=ref), self.assertRaises(ValueError):
                release.target("push", ref)

    def test_untrusted_event_is_rejected(self):
        with self.assertRaises(ValueError):
            release.target("pull_request_target", "refs/heads/main")


if __name__ == "__main__":
    unittest.main()

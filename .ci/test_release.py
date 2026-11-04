import importlib.util
import os
from pathlib import Path
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("release_check", Path(__file__).with_name("check_release.py"))
release = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release)


class ReleaseGuardTests(unittest.TestCase):
    def test_matching_version_tag(self):
        with patch.dict(os.environ, {"GITHUB_REF": "refs/tags/v0.1.0a1"}):
            release.main()

    def test_main_is_not_a_release(self):
        with patch.dict(os.environ, {"GITHUB_REF": "refs/heads/main"}):
            with self.assertRaises(SystemExit):
                release.main()

    def test_tag_for_another_version_is_rejected(self):
        with patch.dict(os.environ, {"GITHUB_REF": "refs/tags/v0.2.0"}):
            with self.assertRaises(SystemExit):
                release.main()


if __name__ == "__main__":
    unittest.main()

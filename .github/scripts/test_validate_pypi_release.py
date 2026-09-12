"""Tests for the release-tag validation helpers."""

import importlib.util
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).with_name("validate_pypi_release.py")
SPEC = importlib.util.spec_from_file_location("validate_pypi_release", SCRIPT_PATH)
assert SPEC and SPEC.loader
release = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release)


class ReleaseValidationTests(unittest.TestCase):
    def test_extracts_version_from_release_tag(self):
        self.assertEqual(release.version_from_release_tag("1.0.0-RELEASE"), "1.0.0")
        self.assertEqual(release.version_from_release_tag("v1.2.3-release"), "1.2.3")

    def test_rejects_invalid_release_tag(self):
        with self.assertRaises(ValueError):
            release.version_from_release_tag("1.0.0")

    def test_requires_version_higher_than_all_published_versions(self):
        release.validate_version("1.0.0", ["0.9.9", "1.0.0rc1"])
        with self.assertRaises(ValueError):
            release.validate_version("1.0.0", ["1.0.0"])
        with self.assertRaises(ValueError):
            release.validate_version("0.9.9", ["1.0.0"])

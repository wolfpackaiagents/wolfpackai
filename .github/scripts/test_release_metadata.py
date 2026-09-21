"""Tests for the helpers that turn a merged release commit into a release tag."""

import importlib.util
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).with_name("release_metadata.py")
SPEC = importlib.util.spec_from_file_location("release_metadata", SCRIPT_PATH)
assert SPEC and SPEC.loader
metadata = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(metadata)


def write_pyproject(directory: str, version: str) -> Path:
    path = Path(directory) / "pyproject.toml"
    path.write_text(f'[project]\nname = "wolfpackai"\nversion = "{version}"\n', encoding="utf-8")
    return path


class ReleaseSubjectTests(unittest.TestCase):
    def test_reads_the_version_from_a_release_subject(self):
        self.assertEqual(metadata.version_from_release_subject("Release 0.2.5"), "0.2.5")
        self.assertEqual(metadata.version_from_release_subject("Release 10.20.30\n"), "10.20.30")

    def test_ignores_subjects_that_are_not_a_plain_release(self):
        for subject in (
            "Release 0.2.5 (dry run)",
            "[dry run] Release 0.2.5",
            "Fix Release 0.2.5 notes",
            "release 0.2.5",
            "Release 0.2",
            "Release v0.2.5",
            "Merge pull request #1 from x/release/0.2.5",
            "",
        ):
            self.assertIsNone(metadata.version_from_release_subject(subject), subject)

    def test_builds_the_release_tag(self):
        self.assertEqual(metadata.release_tag_for("0.2.5"), "0.2.5-RELEASE")


class ReleaseForHeadTests(unittest.TestCase):
    def test_returns_the_tag_when_the_commit_and_the_pyproject_agree(self):
        with tempfile.TemporaryDirectory() as directory:
            pyproject = write_pyproject(directory, "0.2.5")
            self.assertEqual(metadata.release_for_head("Release 0.2.5", pyproject), ("0.2.5", "0.2.5-RELEASE"))

    def test_returns_nothing_for_a_commit_that_is_not_a_release(self):
        with tempfile.TemporaryDirectory() as directory:
            pyproject = write_pyproject(directory, "0.2.5")
            self.assertIsNone(metadata.release_for_head("Fix a typo", pyproject))

    def test_refuses_a_release_commit_whose_pyproject_has_another_version(self):
        with tempfile.TemporaryDirectory() as directory:
            pyproject = write_pyproject(directory, "0.2.3")
            with self.assertRaises(ValueError):
                metadata.release_for_head("Release 0.2.5", pyproject)

    def test_refuses_a_pyproject_without_a_version(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "pyproject.toml"
            path.write_text('[project]\nname = "wolfpackai"\n', encoding="utf-8")
            with self.assertRaises(ValueError):
                metadata.read_pyproject_version(path)


if __name__ == "__main__":
    unittest.main()

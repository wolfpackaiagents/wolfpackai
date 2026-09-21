"""Tests for the helper that records a new package version in a uv.lock without re-resolving."""

import importlib.util
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).with_name("set_lock_version.py")
SPEC = importlib.util.spec_from_file_location("set_lock_version", SCRIPT_PATH)
assert SPEC and SPEC.loader
lock = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(lock)

REPO = Path(__file__).resolve().parents[2]

SAMPLE = '''version = 1
requires-python = ">=3.10"

[[package]]
name = "anyio"
version = "4.5.0"
source = { registry = "https://pypi.org/simple" }

[[package]]
name = "wolfpackai"
version = "0.2.3"
source = { editable = "." }
dependencies = [
    { name = "anyio" },
]

[[package]]
name = "wolfpackai-extras"
version = "0.2.3"
source = { registry = "https://pypi.org/simple" }
'''


class SetLockedVersionTests(unittest.TestCase):
    def test_changes_only_the_version_of_the_named_package(self):
        updated = lock.set_locked_version(SAMPLE, "wolfpackai", "0.2.6")
        before, after = SAMPLE.splitlines(), updated.splitlines()
        changed = [(a, b) for a, b in zip(before, after) if a != b]
        self.assertEqual(changed, [('version = "0.2.3"', 'version = "0.2.6"')])
        self.assertEqual(len(before), len(after))
        self.assertIn('name = "wolfpackai-extras"\nversion = "0.2.3"', updated)

    def test_refuses_a_package_that_is_not_in_the_lockfile(self):
        with self.assertRaises(ValueError):
            lock.set_locked_version(SAMPLE, "missing", "1.0.0")

    def test_refuses_a_package_that_appears_twice(self):
        with self.assertRaises(ValueError):
            lock.set_locked_version(SAMPLE + SAMPLE.split("\n\n", 1)[1], "anyio", "9.9.9")

    def test_rejects_a_version_that_is_not_a_plain_release(self):
        for version in ("", "0.2", "0.2.6\n", "0.2.6-RELEASE", '0.2.6"', "0.2.6rc1"):
            with self.assertRaises(ValueError, msg=version):
                lock.set_locked_version(SAMPLE, "wolfpackai", version)

    def test_writes_the_file_in_place(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "uv.lock"
            path.write_text(SAMPLE, encoding="utf-8")
            lock.set_locked_version_in_file(path, "wolfpackai", "0.2.6")
            self.assertIn('name = "wolfpackai"\nversion = "0.2.6"', path.read_text(encoding="utf-8"))


class RealLockfilesTests(unittest.TestCase):
    """The release workflow edits these two files, so their format must keep working."""

    def test_the_repository_lockfiles_change_by_exactly_one_line(self):
        for relative in ("framework/uv.lock", "control-plane/backend/uv.lock"):
            path = REPO / relative
            text = path.read_text(encoding="utf-8")
            updated = lock.set_locked_version(text, "wolfpackai", "999.0.1")
            before, after = text.splitlines(), updated.splitlines()
            changed = [(a, b) for a, b in zip(before, after) if a != b]
            self.assertEqual(len(before), len(after), relative)
            self.assertEqual(len(changed), 1, relative)
            self.assertEqual(changed[0][1], 'version = "999.0.1"', relative)


if __name__ == "__main__":
    unittest.main()

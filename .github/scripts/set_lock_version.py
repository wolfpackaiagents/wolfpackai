"""Record a new version of one package in a uv.lock, changing that single line and nothing else.

The release workflow bumps framework/pyproject.toml, and the lockfiles that pin the local wolfpackai
(framework/uv.lock and control-plane/backend/uv.lock) must show the same version. Running `uv lock`
for that also re-resolves and reformats the whole file whenever the uv on the runner is newer than
the one that wrote the lockfile, which buries the one-line change under dozens of unrelated ones.
Editing the version line keeps the release pull request to three changed lines, and `uv sync --locked`
afterwards still verifies that the lockfile is consistent.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

PLAIN_VERSION = re.compile(r"\d+\.\d+\.\d+")


def set_locked_version(text: str, package: str, version: str) -> str:
    if not PLAIN_VERSION.fullmatch(version):
        raise ValueError(f"{version!r} is not a plain MAJOR.MINOR.PATCH version.")
    pattern = re.compile(rf'(\[\[package\]\]\nname = "{re.escape(package)}"\nversion = ")[^"\n]+(")')
    found = pattern.findall(text)
    if len(found) != 1:
        raise ValueError(f'Expected exactly one [[package]] entry for "{package}", found {len(found)}.')
    return pattern.sub(rf"\g<1>{version}\g<2>", text)


def set_locked_version_in_file(path: Path, package: str, version: str) -> None:
    text = path.read_text(encoding="utf-8")
    path.write_text(set_locked_version(text, package, version), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("lockfile", type=Path)
    parser.add_argument("package")
    parser.add_argument("version")
    args = parser.parse_args()

    try:
        set_locked_version_in_file(args.lockfile, args.package, args.version)
    except (OSError, ValueError) as error:
        print(f"Could not update {args.lockfile}: {error}", file=sys.stderr)
        return 1
    print(f"{args.lockfile}: {args.package} is now {args.version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

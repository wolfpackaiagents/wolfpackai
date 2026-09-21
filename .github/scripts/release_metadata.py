"""Decide whether the commit that just reached main is a release commit, and which tag it gets.

The publish workflow opens a pull request whose only commit is named "Release X.Y.Z" and bumps the
package version. Once that pull request is merged, the tag workflow runs this script on the new head
commit of main. A tag is only created when the subject says "Release X.Y.Z" and framework/pyproject.toml
really has that version, so a stray commit with a similar subject can never produce a tag.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import tomllib
from pathlib import Path

RELEASE_SUBJECT = re.compile(r"Release (\d+\.\d+\.\d+)")


def version_from_release_subject(subject: str) -> str | None:
    """Return X.Y.Z for a subject that is exactly "Release X.Y.Z", otherwise None."""
    match = RELEASE_SUBJECT.fullmatch(subject.strip())
    return match.group(1) if match else None


def release_tag_for(version: str) -> str:
    return f"{version}-RELEASE"


def read_pyproject_version(path: Path) -> str:
    with path.open("rb") as handle:
        data = tomllib.load(handle)
    version = data.get("project", {}).get("version")
    if not isinstance(version, str) or not version:
        raise ValueError(f"{path} has no [project] version.")
    return version


def release_for_head(subject: str, pyproject: Path) -> tuple[str, str] | None:
    """Return (version, tag) for a release commit, None for any other commit."""
    version = version_from_release_subject(subject)
    if version is None:
        return None
    declared = read_pyproject_version(pyproject)
    if declared != version:
        raise ValueError(f'The commit says "Release {version}" but {pyproject} declares version {declared}.')
    return version, release_tag_for(version)


def write_output(name: str, value: str) -> None:
    output_path = os.environ.get("GITHUB_OUTPUT")
    if output_path:
        with open(output_path, "a", encoding="utf-8") as output:
            output.write(f"{name}={value}\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("subject", help="Subject line of the head commit")
    parser.add_argument("pyproject", type=Path, help="Path to framework/pyproject.toml")
    args = parser.parse_args()

    try:
        release = release_for_head(args.subject, args.pyproject)
    except ValueError as error:
        print(f"Release check failed: {error}", file=sys.stderr)
        return 1

    if release is None:
        write_output("is_release", "false")
        print("The head commit is not a release commit; no tag to create.")
        return 0

    version, tag = release
    write_output("is_release", "true")
    write_output("version", version)
    write_output("release_tag", tag)
    print(f"Release commit for {version}; tag {tag}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

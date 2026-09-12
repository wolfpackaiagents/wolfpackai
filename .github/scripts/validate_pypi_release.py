"""Validate a release tag against the versions already published on PyPI."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from typing import Iterable
from urllib.error import HTTPError
from urllib.request import urlopen

from packaging.version import InvalidVersion, Version


RELEASE_TAG = re.compile(r"^v?(\d+\.\d+\.\d+)-RELEASE$", re.IGNORECASE)


def version_from_release_tag(release_tag: str) -> str:
    """Return the PyPI-compatible version represented by a release tag."""
    match = RELEASE_TAG.fullmatch(release_tag.strip())
    if not match:
        raise ValueError("Release tag must use MAJOR.MINOR.PATCH-RELEASE, for example 1.0.0-RELEASE.")
    return str(Version(match.group(1)))


def validate_version(version: str, published_versions: Iterable[str]) -> None:
    """Require the new version to be greater than every PyPI release."""
    candidate = Version(version)
    parsed_versions = [Version(published) for published in published_versions]
    if not parsed_versions:
        return
    latest = max(parsed_versions)
    if candidate <= latest:
        raise ValueError(f"Release version {candidate} must be greater than the latest PyPI version {latest}.")


def published_versions(package: str) -> list[str]:
    url = f"https://pypi.org/pypi/{package}/json"
    try:
        with urlopen(url, timeout=15) as response:  # noqa: S310 -- fixed PyPI API URL
            payload = json.load(response)
    except HTTPError as error:
        if error.code == 404:
            return []
        raise RuntimeError(f"Could not query PyPI for {package}: {error}") from error
    return list(payload["releases"])


def write_output(name: str, value: str) -> None:
    output_path = os.environ.get("GITHUB_OUTPUT")
    if output_path:
        with open(output_path, "a", encoding="utf-8") as output:
            output.write(f"{name}={value}\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("release_tag")
    parser.add_argument("--package", default="wolfpackai")
    args = parser.parse_args()
    release_tag = args.release_tag.strip()

    try:
        version = version_from_release_tag(release_tag)
        validate_version(version, published_versions(args.package))
    except (InvalidVersion, ValueError, RuntimeError) as error:
        print(f"Release validation failed: {error}", file=sys.stderr)
        return 1

    write_output("version", version)
    write_output("release_tag", release_tag)
    print(f"Validated {release_tag}: package version {version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Minimal `python -m wolfpack` CLI to verify the install."""

from __future__ import annotations

import sys


def main() -> None:
    print(f"wolfpack {__import__('wolfpack').__name__} instalado. Python {sys.version_info.major}.{sys.version_info.minor}")


if __name__ == "__main__":
    main()
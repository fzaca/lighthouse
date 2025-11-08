#!/usr/bin/env python3
r"""Extract a version section from CHANGELOG.md to use as release notes.

Example:
    poetry run python scripts/generate_release_notes.py \\
        --version 0.4.0 --output dist/release-notes/v0.4.0.md
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional


def parse_args() -> argparse.Namespace:
    """Return CLI arguments."""
    parser = argparse.ArgumentParser(
        description=(
            "Extract release notes for a given version from CHANGELOG.md."
        )
    )
    parser.add_argument(
        "--version",
        help="Version to extract. Defaults to the version in pyproject.toml.",
    )
    parser.add_argument(
        "--changelog",
        default="CHANGELOG.md",
        help="Path to the changelog file (default: CHANGELOG.md).",
    )
    parser.add_argument(
        "--pyproject",
        default="pyproject.toml",
        help="Path to pyproject.toml (used when --version is omitted).",
    )
    parser.add_argument(
        "--output",
        help=(
            "Optional path to write the extracted notes. Prints to stdout "
            "when omitted."
        ),
    )
    parser.add_argument(
        "--no-header",
        action="store_true",
        help="Exclude the version header line from the output.",
    )
    return parser.parse_args()


def read_version_from_pyproject(path: Path) -> str:
    """Locate the Poetry version inside pyproject.toml."""
    version: Optional[str] = None
    in_poetry_block = False
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("["):
            in_poetry_block = line == "[tool.poetry]"
            continue
        if in_poetry_block and line.startswith("version"):
            _, value = line.split("=", 1)
            version = value.strip().strip('"').strip("'")
            break
    if not version:
        raise SystemExit(
            f"Failed to detect the project version inside {path}. "
            "Pass --version explicitly."
        )
    return version


def extract_notes(
    changelog: Path, version: str, include_header: bool
) -> str:
    """Return the changelog section for the requested version."""
    lines = changelog.read_text(encoding="utf-8").splitlines()
    header_prefix = f"## {version}"
    collected: list[str] = []
    capture = False

    for line in lines:
        if line.startswith("## "):
            if capture:
                break
            if line.startswith(header_prefix):
                capture = True
                if include_header:
                    collected.append(line.rstrip())
                continue
        if capture:
            collected.append(line.rstrip())

    if not collected:
        raise SystemExit(
            "Could not find a changelog section for version "
            f"{version} inside {changelog}."
        )
    # Trim leading/trailing blank lines.
    while collected and collected[0] == "":
        collected.pop(0)
    while collected and collected[-1] == "":
        collected.pop()
    return "\n".join(collected) + "\n"


def main() -> None:
    """CLI entrypoint."""
    args = parse_args()
    changelog_path = Path(args.changelog)
    if not changelog_path.exists():
        raise SystemExit(f"Changelog not found: {changelog_path}")
    if args.version:
        version = args.version
    else:
        version = read_version_from_pyproject(Path(args.pyproject))

    notes = extract_notes(
        changelog=changelog_path,
        version=version,
        include_header=not args.no_header,
    )

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(notes, encoding="utf-8")
        print(f"Wrote release notes for {version} to {output_path}")
    else:
        print(notes, end="")


if __name__ == "__main__":
    main()

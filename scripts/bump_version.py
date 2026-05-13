#!/usr/bin/env python3
"""Bump the project version, commit it, and create an annotated Git tag."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = ROOT / "pyproject.toml"
INIT = ROOT / "src" / "ais_mcp" / "__init__.py"
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")
GIT = ["git", "--git-dir=.repo.git", "--work-tree=."]


def run(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=ROOT,
        check=check,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def current_version() -> str:
    match = re.search(r'^version = "([^"]+)"$', PYPROJECT.read_text(), re.MULTILINE)
    if not match:
        raise SystemExit("Could not find project.version in pyproject.toml")
    return match.group(1)


def next_version(version: str, bump: str) -> str:
    major, minor, patch = (int(part) for part in version.split("."))
    if bump == "major":
        return f"{major + 1}.0.0"
    if bump == "minor":
        return f"{major}.{minor + 1}.0"
    if bump == "patch":
        return f"{major}.{minor}.{patch + 1}"
    if VERSION_RE.fullmatch(bump):
        return bump
    raise SystemExit("Use major, minor, patch, or an explicit X.Y.Z version")


def replace_version(path: Path, pattern: str, replacement: str) -> None:
    text = path.read_text()
    updated, count = re.subn(pattern, replacement, text, count=1, flags=re.MULTILINE)
    if count != 1:
        raise SystemExit(f"Could not update version in {path}")
    path.write_text(updated)


def ensure_clean_tree() -> None:
    status = run([*GIT, "status", "--porcelain"]).stdout.strip()
    if status:
        raise SystemExit("Working tree is not clean. Commit or stash changes first.")


def ensure_tag_missing(tag: str) -> None:
    result = run([*GIT, "rev-parse", "-q", "--verify", f"refs/tags/{tag}"], check=False)
    if result.returncode == 0:
        raise SystemExit(f"Tag already exists: {tag}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("bump", help="major, minor, patch, or explicit X.Y.Z")
    parser.add_argument("--no-push", action="store_true", help="Do not push commit and tag")
    args = parser.parse_args()

    ensure_clean_tree()
    old_version = current_version()
    new_version = next_version(old_version, args.bump)
    tag = f"v{new_version}"
    ensure_tag_missing(tag)

    replace_version(PYPROJECT, r'^version = "[^"]+"$', f'version = "{new_version}"')
    replace_version(INIT, r'^__version__ = "[^"]+"$', f'__version__ = "{new_version}"')

    run([*GIT, "add", str(PYPROJECT.relative_to(ROOT)), str(INIT.relative_to(ROOT))])
    run([*GIT, "commit", "-m", f"Bump version to {new_version}"])
    run([*GIT, "tag", "-a", tag, "-m", f"Release {tag}"])

    if not args.no_push:
        run([*GIT, "push"])
        run([*GIT, "push", "origin", tag])

    print(f"Bumped {old_version} -> {new_version} and created {tag}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

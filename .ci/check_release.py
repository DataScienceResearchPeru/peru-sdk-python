"""Require a release tag to match the Python project version."""
import os
from pathlib import Path
import tomllib

ROOT = Path(__file__).resolve().parents[1]


def main():
    version = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
    expected = "refs/tags/v" + version
    if os.environ.get("GITHUB_REF") != expected:
        raise SystemExit(f"Publishing requires tag v{version}; project/tag mismatch")
    print("Release tag matches project version:", version)


if __name__ == "__main__":
    main()

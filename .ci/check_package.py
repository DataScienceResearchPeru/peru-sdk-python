"""Build, audit and test Python distributions in isolation from the source checkout."""
import argparse
import email.parser
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import tomllib
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    dist, metadata = output / "dist", output / "manifest"
    if output.exists() and any(output.iterdir()):
        raise SystemExit("distribution destination must be empty")
    dist.mkdir(parents=True)
    metadata.mkdir()
    Path("/var/tmp").mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="peru-python-package-", dir="/var/tmp") as directory:
        task = Path(directory)
        env = {**os.environ, "TMPDIR": directory, "TEMP": directory, "TMP": directory,
               "PYTHONDONTWRITEBYTECODE": "1", "PIP_DISABLE_PIP_VERSION_CHECK": "1"}

        def run(*command, cwd=task, extra=None):
            subprocess.run(command, cwd=cwd, env={**env, **(extra or {})}, check=True)

        source = task / "source"
        shutil.copytree(ROOT, source, ignore=shutil.ignore_patterns(".git", "__pycache__", "*.egg-info", "build", "dist"))
        project = tomllib.loads((source / "pyproject.toml").read_text())["project"]
        run(sys.executable, "-m", "build", str(source), "--outdir", str(dist))
        wheel, = dist.glob("*.whl")
        sdist, = dist.glob("*.tar.gz")
        with zipfile.ZipFile(wheel) as archive:
            names = archive.namelist()
            if len(names) != len(set(names)):
                raise SystemExit("duplicate wheel entries")
            metadata_name, = [name for name in names if name.endswith(".dist-info/METADATA")]
            info_root = metadata_name.rsplit("/", 1)[0] + "/"
            for name in names:
                if ".." in Path(name).parts or not name.startswith(("peru_sdk/", info_root)):
                    raise SystemExit(f"unexpected wheel file: {name}")
                if name.endswith((".go", ".java", ".so", ".pyd", ".dll", ".whl", ".jar")):
                    raise SystemExit(f"foreign implementation or binary in wheel: {name}")
            fields = email.parser.BytesParser().parsebytes(archive.read(metadata_name))
            if fields["Name"] != project["name"] or fields["Version"] != project["version"] or fields.get_all("Requires-Dist"):
                raise SystemExit("unexpected package identity, version or runtime dependencies")
        extracted = task / "sdist"
        with tarfile.open(sdist) as archive:
            for member in archive.getmembers():
                path = Path(member.name)
                if path.is_absolute() or ".." in path.parts or not (member.isfile() or member.isdir()):
                    raise SystemExit("unsafe source archive entry")
                target = extracted / path
                if member.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(archive.extractfile(member).read())
        package_root, = extracted.iterdir()
        if not (package_root / "tests/data/conformance.json").is_file():
            raise SystemExit("source distribution is missing its independent test corpus")
        for path in package_root.rglob("*"):
            if path.suffix in (".go", ".java", ".jar", ".whl") or path.name in ("go.mod", "sdk-go"):
                raise SystemExit("foreign SDK in source distribution")
        site = task / "installed"
        run(sys.executable, "-m", "pip", "install", "--no-deps", "--no-cache-dir", "--only-binary=:all:",
            "--target", str(site), str(wheel))
        extra = {"PYTHONPATH": str(site)}
        run(sys.executable, "-c", "import peru_sdk; from pathlib import Path; assert Path(peru_sdk.__file__).is_relative_to(Path('installed').resolve())", extra=extra)
        run(sys.executable, "-m", "unittest", "discover", "-s", str(package_root / "tests"), "-v", extra=extra)
        run(sys.executable, "-m", "twine", "check", "--strict", str(wheel), str(sdist))
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    release = {"project": project["name"], "version": project["version"], "commit": commit,
               "upstreams": json.loads((ROOT / "upstream.lock.json").read_text())}
    (metadata / "release.json").write_text(json.dumps(release, indent=2) + "\n")
    sums = []
    for path in sorted(output.rglob("*")):
        if path.is_file():
            sums.append(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.relative_to(output).as_posix()}")
    (metadata / "SHA256SUMS").write_text("\n".join(sums) + "\n")
    print("Verified isolated Python distributions:", output)


if __name__ == "__main__":
    main()

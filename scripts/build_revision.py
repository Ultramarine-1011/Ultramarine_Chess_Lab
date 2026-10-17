"""Build a clean historical UCL commit in an isolated temporary Git worktree.

Usage: python scripts/build_revision.py <full-or-resolvable-revision>
Retains binary, SHA-256, --build-info, exact commands and compiler output under
.tools/engines/<full-sha>/, then removes the temporary checkout.
"""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))
from ucl.records import sha256, write_json


def build_revision(revision, output=None):
    """Build/reuse a clean revision; optional output supports platform-specific caches."""
    full = subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "--verify", revision + "^{commit}"], text=True).strip()
    output = Path(output) if output is not None else ROOT / ".tools" / "engines" / full
    manifest_path = output / 'manifest.json'
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if sha256(manifest['binary']) != manifest['sha256']:
            raise ValueError('cached binary differs from its manifest')
        print(manifest_path)
        return manifest_path
    output.mkdir(parents=True, exist_ok=True)
    commands = []
    with tempfile.TemporaryDirectory(prefix="ucl-revision-") as tmp:
        source = Path(tmp) / "source"
        build = Path(tmp) / "build"
        def run(args, log):
            commands.append([str(a) for a in args])
            subprocess.run(commands[-1], stdout=log, stderr=subprocess.STDOUT, check=True)
        with (output / "build.log").open("w") as log:
            try:
                run(["git", "-C", ROOT, "worktree", "add", "--detach", source, full], log)
                run(["cmake", "-S", source, "-B", build, "-G", "Ninja", "-DBUILD_TESTING=OFF", "-DCMAKE_BUILD_TYPE=Release"], log)
                run(["cmake", "--build", build, "--parallel", "4"], log)
                binary = output / ("ucl.exe" if sys.platform == "win32" else "ucl")
                shutil.copy2(build / binary.name, binary)
                info = json.loads(subprocess.check_output([str(binary), "--build-info"], text=True, timeout=10))
                if info["revision"] != full or info["dirty"]:
                    raise ValueError("historical binary provenance mismatch")
                write_json(output / "manifest.json", {"binary": str(binary), "sha256": sha256(binary), "build_info": info, "commands": commands})
            finally:
                if source.exists():
                    run(["git", "-C", ROOT, "worktree", "remove", source], log)
    print(output / "manifest.json")
    return output / "manifest.json"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("revision")
    build_revision(parser.parse_args().revision)

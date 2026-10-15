#!/usr/bin/env python3
"""Build a pinned fastchess in .tools (macOS/Linux or Windows MSYS2 shell)."""
import argparse
from pathlib import Path
import shutil
import subprocess
import sys

REVISION = "ebfd64cb7fac80d4822c50b07dca4fe934779d21"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jobs", type=int, default=4)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    source = root / ".tools/fastchess-src"
    binary = "fastchess.exe" if sys.platform == "win32" else "fastchess"
    if not shutil.which("make") or not shutil.which("g++"):
        parser.exit(1, "Install make and a C++17 compiler; Windows: use MSYS2 UCRT64 with make and g++.\n")
    source.parent.mkdir(exist_ok=True)
    if not source.exists():
        subprocess.run(["git", "init", str(source)], check=True)
        subprocess.run(["git", "-C", str(source), "remote", "add", "origin", "https://github.com/Disservin/fastchess.git"], check=True)
    if subprocess.check_output(["git", "-C", str(source), "status", "--porcelain"], text=True).strip():
        parser.exit(1, "fastchess source has changes; preserve them before rebuilding.\n")
    subprocess.run(["git", "-C", str(source), "fetch", "--depth", "1", "origin", REVISION], check=True)
    subprocess.run(["git", "-C", str(source), "checkout", "--detach", REVISION], check=True)
    subprocess.run(["make", f"-j{args.jobs}"], cwd=source, check=True)
    target = root / ".tools/bin" / binary
    target.parent.mkdir(exist_ok=True)
    shutil.copy2(source / binary, target)
    subprocess.run([str(target), "--version"], check=True)
    print(target)


if __name__ == "__main__":
    main()

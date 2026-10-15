"""Portable, versioned metadata and atomic JSON records."""
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
import uuid

from jsonschema import Draft202012Validator, FormatChecker


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def sha256(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def git_state(root):
    def git(*args):
        return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()
    return {"revision": git("rev-parse", "HEAD"),
            "dirty": bool(git("status", "--porcelain", "--untracked-files=normal"))}


def hardware():
    memory = None
    cpu = platform.processor() or platform.machine()
    if sys.platform == "darwin":
        memory = int(subprocess.check_output(["sysctl", "-n", "hw.memsize"], text=True))
        cpu = subprocess.check_output(["sysctl", "-n", "machdep.cpu.brand_string"], text=True).strip()
    elif sys.platform == "win32":
        import ctypes

        class MemoryStatus(ctypes.Structure):
            _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong),
                        ("total", ctypes.c_ulonglong)] + [(f"unused{i}", ctypes.c_ulonglong) for i in range(6)]
        status = MemoryStatus()
        status.length = ctypes.sizeof(status)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            memory = status.total
    elif hasattr(os, "sysconf"):
        memory = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
    return {"os": platform.platform(), "architecture": platform.machine(), "cpu": cpu,
            "logical_cpus": os.cpu_count(), "memory_bytes": memory,
            "python": platform.python_version(),
            "packages": {name: importlib.metadata.version(name) for name in ("chess", "jsonschema", "ucl-lab")}}


def prepare_output(root, output, overwrite=False):
    """Replace disposable runs only; archived or tracked evidence stays intact."""
    output = Path(output).resolve()
    if output.exists() and overwrite:
        record = json.loads((output / 'record.json').read_text(encoding='utf-8'))
        if record.get('mode') != 'exploratory':
            raise ValueError('only exploratory runs can be overwritten')
        root = Path(root).resolve()
        if output == root or output in root.parents:
            raise ValueError('output cannot contain the repository')
        if output.is_relative_to(root) and subprocess.check_output(
                ['git', '-C', str(root), 'ls-files', '--', output.relative_to(root).as_posix()]):
            raise ValueError('tracked experiment evidence cannot be overwritten')
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=False)


def new_record(root, config, formal=False):
    return {"schema_version": 1, "id": str(uuid.uuid4()), "kind": "match",
            "mode": "formal" if formal else "exploratory",
            "status": "running", "started_at": utc_now(), "finished_at": None,
            "code": git_state(root), "parameters": config, "seed": config["seed"],
            "hardware": hardware(), "tools": {}, "engines": [], "artifacts": {},
            "results": None, "error": None}


def validate_record(record, schema):
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(record)


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="\n", dir=path.parent, delete=False) as stream:
            temp = Path(stream.name)
            json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)
            stream.write("\n")
        temp.replace(path)
    finally:
        if temp and temp.exists():
            temp.unlink()

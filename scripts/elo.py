#!/usr/bin/env python3
"""Daily workspace vs cached baseline: python scripts/elo.py [--games 128]."""
import argparse
import json
import math
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))
from build_revision import build_revision
from ucl.integrity import validate_bundle
from ucl.match import executable, run_match
from ucl.records import sha256, write_json
from ucl.report import elo_equivalent, markdown_report

STATE = ROOT / ".tools" / "elo"
OPENINGS = ROOT / "experiments" / "openings" / "elo-dev.epd"
BINARY = "ucl.exe" if sys.platform == "win32" else "ucl"


def baseline_binary(revision):
    """Build once per platform/architecture/SHA; never silently use a stale binary."""
    full = subprocess.check_output(
        ["git", "-C", str(ROOT), "rev-parse", "--verify", "--end-of-options", revision + "^{commit}"],
        text=True).strip()
    directory = STATE / "baselines" / f"{sys.platform}-{platform.machine()}" / full
    manifest_path = directory / "manifest.json"
    if not manifest_path.exists():
        # Only this cache entry is disposable, including an interrupted build.
        if directory.exists():
            shutil.rmtree(directory)
        print(f"Building baseline {full} ...", flush=True)
        build_revision(full, output=directory)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    binary = directory / BINARY
    info = manifest["build_info"]
    if (info["revision"] != full or info["dirty"] or info["build_type"] != "Release"
            or sha256(binary) != manifest["sha256"]):
        raise ValueError(f"baseline cache mismatch: remove {directory} and retry")
    print(f"Baseline: {full} (cached)", flush=True)
    return full, binary


def build_candidate():
    directory = STATE / "candidate-build"
    commands = [
        ["cmake", "-S", str(ROOT), "-B", str(directory), "-G", "Ninja",
         "-DBUILD_TESTING=OFF", "-DCMAKE_BUILD_TYPE=Release"],
        ["cmake", "--build", str(directory), "--target", "ucl", "--parallel", "4"],
    ]
    print("Building workspace candidate (incremental Release) ...", flush=True)
    with (STATE / "candidate-build.log").open("w", encoding="utf-8") as log:
        for args in commands:
            subprocess.run(args, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, check=True)
    binary = directory / BINARY
    info = json.loads(subprocess.check_output([str(binary), "--build-info"], text=True, timeout=10))
    if info["build_type"] != "Release":
        raise ValueError("candidate must be a Release build")
    write_json(STATE / "candidate.json", {"binary": str(binary), "sha256": sha256(binary),
                                         "build_info": info, "commands": commands})
    return binary


def time_control(value):
    # Standard fastchess sudden-death forms: seconds[+inc] or minutes:seconds[+inc].
    if not re.fullmatch(r"(?:\d+:)?\d+(?:\.\d+)?(?:\+\d+(?:\.\d+)?)?", value):
        raise argparse.ArgumentTypeError("use seconds[+increment] or minutes:seconds[+increment]")
    base, _, increment = value.partition("+")
    minutes, colon, seconds = base.partition(":")
    base_seconds = float(minutes) * 60 + float(seconds) if colon else float(base)
    inc_seconds = float(increment or 0)
    if not math.isfinite(base_seconds + inc_seconds) or base_seconds <= 0:
        raise argparse.ArgumentTypeError("time control must have a finite positive base time")
    return value, base_seconds, inc_seconds


def match_config(candidate, baseline, revision, games, tc, concurrency):
    value, seconds, increment = tc
    return {
        "version": 1, "comparison": "smoke", "seed": 20261017,
        "engines": [
            {"name": name, "path": str(binary), "revision": sha, "build": description,
             "ucl_build_info": True, "options": {"MoveOverhead": 10}}
            for name, binary, sha, description in (
                ("Candidate", candidate, "HEAD", "CMake Ninja Release; current workspace"),
                ("Baseline", baseline, revision, "CMake Ninja Release; isolated clean revision"))
        ],
        "rounds": games // 2, "games": 2, "tc": value, "concurrency": concurrency,
        "openings": {"path": str(OPENINGS), "format": "epd", "order": "sequential"},
        "maxmoves": 150,
        "timeout_seconds": max(120, math.ceil(games / concurrency) * math.ceil(2 * (seconds + 150 * increment) + 10)),
    }


def result_report(record):
    r = record["results"]
    ci = r["score_ci95_paired_bootstrap"]
    def number(value):
        return f"{value:+.2f}" if isinstance(value, (int, float)) else value
    score_ci = f"[{ci[0]:.2%}, {ci[1]:.2%}]" if ci else "unavailable (fewer than two pairs)"
    elo_ci = f"[{number(elo_equivalent(ci[0]))}, {number(elo_equivalent(ci[1]))}]" if ci else "unavailable"
    return (markdown_report(record) + "\nDaily development comparison:\n\n"
            f"W/D/L: {r['wins']}/{r['draws']}/{r['losses']}; score: {r['score']:.2%}\n\n"
            f"Relative Elo: {number(elo_equivalent(r['score']))}; paired bootstrap 95% CI: {elo_ci}\n\n"
            f"Score paired bootstrap 95% CI: {score_ci}\n\n"
            "Elo is the logistic transform of score and its paired interval; descriptive only.\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--set-baseline", metavar="REVISION", help="cache and save baseline SHA, then exit")
    parser.add_argument("--games", type=int, default=128, help="total games, positive even number (default: 128)")
    parser.add_argument("--tc", type=time_control, default="2+0.02", help="fastchess time control (default: 2+0.02)")
    parser.add_argument("--concurrency", type=int, default=4, help="parallel games (default: 4)")
    args = parser.parse_args(argv)
    if args.games <= 0 or args.games % 2:
        parser.error("--games must be a positive even number")
    if args.concurrency <= 0:
        parser.error("--concurrency must be positive")
    try:
        STATE.mkdir(parents=True, exist_ok=True)
        saved = STATE / "baseline.json"
        if args.set_baseline:
            revision, _ = baseline_binary(args.set_baseline)
            write_json(saved, {"revision": revision})
            print(f"Saved baseline: {saved}")
            return
        openings = [line for line in OPENINGS.read_text(encoding="utf-8").splitlines() if line.strip()]
        if args.games // 2 > len(openings):
            parser.error(f"--games exceeds the development opening set ({2 * len(openings)} games)")
        # Prefer the repository's pinned fastchess, then an installed executable.
        local_fastchess = ROOT / ".tools" / "bin" / ("fastchess.exe" if sys.platform == "win32" else "fastchess")
        fastchess = executable(str(local_fastchess) if local_fastchess.is_file() else "fastchess", ROOT)
        if not saved.exists():
            print("No baseline set; pinning current committed HEAD (workspace edits remain Candidate only).", flush=True)
        revision, baseline = baseline_binary(json.loads(saved.read_text(encoding="utf-8"))["revision"] if saved.exists() else "HEAD")
        if not saved.exists():
            write_json(saved, {"revision": revision})
        candidate = build_candidate()
        config = match_config(candidate, baseline, revision, args.games, args.tc, args.concurrency)
        config_path = STATE / "match.json"
        write_json(config_path, config)
        output = STATE / "latest"
        print(f"Playing {args.games} games, tc={config['tc']}, concurrency={args.concurrency} ...", flush=True)
        record = run_match(ROOT, config_path, output, str(fastchess), overwrite=True)
        if record["status"] != "completed":
            raise ValueError(f"{record['error']}; retained diagnostics: {output}")
        schema = json.loads((ROOT / "schemas" / "experiment-v1.schema.json").read_text(encoding="utf-8"))
        record = validate_bundle(output / "record.json", schema)
        report = result_report(record)
        (output / "report.md").write_text(report, encoding="utf-8")
        print(report)
        print(f"Results / PGN / versions / config: {output}")
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        parser.exit(1, f"error: {exc}\nBuild logs: {STATE}\n")


if __name__ == "__main__":
    main()

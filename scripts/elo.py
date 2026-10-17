#!/usr/bin/env python3
"""Daily UCL vs limited Stockfish: python scripts/elo.py [--sf-elo 1600]."""
import argparse
import json
import math
from pathlib import Path
import os
import re
import shutil
import subprocess
import sys

import chess.engine

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))
from ucl.integrity import validate_bundle
from ucl.match import executable, run_match
from ucl.records import sha256, write_json
from ucl.report import elo_equivalent, markdown_report

STATE = ROOT / ".tools" / "elo"
OPENINGS = ROOT / "experiments" / "openings" / "elo-dev.epd"
BINARY = "ucl.exe" if sys.platform == "win32" else "ucl"
SF_VERSION = "Stockfish 17.1"
SF_RELEASE = "https://github.com/official-stockfish/Stockfish/releases/tag/sf_17.1"


def find_stockfish(value=None):
    if value is not None:
        return executable(value, ROOT)
    name = "stockfish.exe" if sys.platform == "win32" else "stockfish"
    r6 = sorted((ROOT / ".tools" / "r6-stockfish").rglob("stockfish*"))
    candidates = [p for p in r6 if p.is_file() and (
        p.suffix == ".exe" if sys.platform == "win32" else p.suffix != ".exe" and os.access(p, os.X_OK))]
    candidates += [ROOT / ".tools" / "bin" / name.replace("stockfish", "stockfish-17.1"),
                   ROOT / ".tools" / "bin" / name]
    installed = shutil.which("stockfish")
    if installed:
        candidates.append(Path(installed))
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise FileNotFoundError(
        f"Stockfish 17.1 not found. Download a binary for your OS/CPU from {SF_RELEASE}; "
        f"unpack under .tools/r6-stockfish/ or pass --stockfish /path/to/{name}")


def stockfish_identity(path, elo, pinned=True):
    options = {"UCI_LimitStrength": True, "UCI_Elo": elo, "Threads": 1, "Hash": 16}
    with chess.engine.SimpleEngine.popen_uci(str(path), timeout=10) as client:
        version = client.id.get("name", "")
        if not version.startswith("Stockfish ") or (pinned and version != SF_VERSION):
            raise ValueError(f"default opponent must be {SF_VERSION}; found {version!r}. "
                             "Use --stockfish PATH to explicitly choose another Stockfish version.")
        for name, value in options.items():
            option = client.options.get(name)
            kind = "check" if name == "UCI_LimitStrength" else "spin"
            if option is None or option.type != kind:
                raise ValueError(f"{version} must support UCI option {name} ({kind})")
            if kind == "spin" and (option.min is None or option.max is None or not option.min <= value <= option.max):
                raise ValueError(f"{name}={value} outside {version} supported range [{option.min}, {option.max}]")
        client.configure(options)
        client.ping()
        identity = {"version": version, "uci_id": dict(client.id), "options": options,
                    "uci_elo_range": [client.options["UCI_Elo"].min, client.options["UCI_Elo"].max]}
    return identity


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


def match_config(candidate, stockfish, identity, games, tc, concurrency):
    value, seconds, increment = tc
    return {
        "version": 1, "comparison": "smoke", "seed": 20261017, "strict": False,
        "engines": [
            {"name": "UCL", "path": str(candidate), "revision": "HEAD", "ucl_build_info": True,
             "build": "CMake Ninja Release; current workspace", "options": {"MoveOverhead": 10}},
            {"name": identity["version"], "path": str(stockfish), "revision": None,
             "version": identity["version"], "build": "External Stockfish UCI binary",
             "options": identity["options"]},
        ],
        "rounds": games // 2, "games": 2, "tc": value, "concurrency": concurrency,
        "openings": {"path": str(OPENINGS), "format": "epd", "order": "sequential"},
        "maxmoves": 150,
        "timeout_seconds": max(120, math.ceil(games / concurrency) * math.ceil(2 * (seconds + 150 * increment) + 10)),
    }


def result_report(record):
    r = record["results"]
    ci = r["score_ci95_paired_bootstrap"]
    sf = record["engines"][1]
    config = record["parameters"]
    target = sf["options"]["UCI_Elo"]
    def number(value, offset=0):
        return f"{value + offset:+.2f}" if isinstance(value, (int, float)) else value
    difference = elo_equivalent(r["score"])
    score_ci = f"[{ci[0]:.2%}, {ci[1]:.2%}]" if ci else "unavailable (fewer than two pairs)"
    elo_ci = f"[{number(elo_equivalent(ci[0]))}, {number(elo_equivalent(ci[1]))}]" if ci else "unavailable"
    rating = "unavailable (boundary score or insufficient paired variation)"
    if 0 < r["score"] < 1 and ci and ci[0] < ci[1]:
        rating = (f"{number(difference, target)}; paired bootstrap 95% CI: "
                  f"[{number(elo_equivalent(ci[0]), target)}, {number(elo_equivalent(ci[1]), target)}]")
    return (markdown_report(record) + "\nDaily development comparison:\n\n"
            f"Opponent: {sf['version']}; binary SHA256: `{sf['sha256']}`\n\n"
            f"Stockfish UCI: {sf['options']}; tc={config['tc']}; concurrency={config['concurrency']}\n\n"
            f"W/D/L: {r['wins']}/{r['draws']}/{r['losses']}; score: {r['score']:.2%}\n\n"
            f"Relative Elo vs Stockfish: {number(difference)}; paired bootstrap 95% CI: {elo_ci}\n\n"
            f"Score paired bootstrap 95% CI: {score_ci}\n\n"
            f"Approximate rating (Stockfish target {target} + relative Elo): {rating}\n\n"
            "Stockfish limited-strength reference scale only; not a FIDE or Chess.com absolute rating. "
            "Conditional on version, time control, openings and hardware; small-sample intervals are descriptive.\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stockfish", metavar="PATH", help="Stockfish executable (default: fixed Stockfish 17.1)")
    parser.add_argument("--sf-elo", type=int, default=1600, help="Stockfish UCI_Elo target (default: 1600)")
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
        openings = [line for line in OPENINGS.read_text(encoding="utf-8").splitlines() if line.strip()]
        if args.games // 2 > len(openings):
            parser.error(f"--games exceeds the development opening set ({2 * len(openings)} games)")
        # Prefer the repository's pinned fastchess, then an installed executable.
        local_fastchess = ROOT / ".tools" / "bin" / ("fastchess.exe" if sys.platform == "win32" else "fastchess")
        fastchess = executable(str(local_fastchess) if local_fastchess.is_file() else "fastchess", ROOT)
        stockfish = find_stockfish(args.stockfish)
        identity = stockfish_identity(stockfish, args.sf_elo, pinned=args.stockfish is None)
        write_json(STATE / "stockfish.json", {"path": str(stockfish), "sha256": sha256(stockfish), **identity})
        print(f"Opponent: {identity['version']}, UCI_Elo={args.sf_elo}, Threads=1, Hash=16 MiB", flush=True)
        candidate = build_candidate()
        config = match_config(candidate, stockfish, identity, args.games, args.tc, args.concurrency)
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
    except (OSError, ValueError, KeyError, subprocess.SubprocessError, chess.engine.EngineError) as exc:
        parser.exit(1, f"error: {exc}\nBuild logs: {STATE}\n")


if __name__ == "__main__":
    main()

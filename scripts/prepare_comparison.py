"""Create paired match and fixed-depth benchmark configs from two build manifests."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))
from ucl.match import validate_comparison
from ucl.records import sha256, write_json


def prepare(baseline, candidate, output):
    manifests = [json.loads(Path(p).read_text()) for p in (candidate, baseline)]
    entries = []
    for name, manifest in zip(("R2", "R1"), manifests, strict=True):
        binary = Path(manifest["binary"])
        if sha256(binary) != manifest["sha256"]:
            raise ValueError("build manifest binary hash mismatch")
        entries.append({"name": name, "path": str(binary), "revision": manifest["build_info"]["revision"],
                        "build": "CMake Release; isolated clean Git worktree", "ucl_build_info": True,
                        "options": {"MoveOverhead": 0}})
    entries[0]["options"].update(Quiescence=True, UseTT=True, PVOrdering=True, Hash=16)
    validate_comparison({"comparison": "revision"}, [dict(e, sha256=m["sha256"], build_info=m["build_info"]) for e, m in zip(entries, manifests, strict=True)])
    output = Path(output); output.mkdir(parents=True, exist_ok=True)
    write_json(output / "match.json", {"version": 1, "comparison": "revision", "seed": 20261015,
        "engines": entries, "rounds": 8, "games": 2, "concurrency": 1, "tc": "30+0.1", "depth": 4,
        "openings": {"path": "experiments/openings/r2.epd", "format": "epd", "order": "sequential"},
        "maxmoves": 100, "timeout_seconds": 600})
    reference = {**entries[0], "name": "R2-reference", "options": {"MoveOverhead": 0, "Quiescence": False, "UseTT": False, "PVOrdering": False, "Hash": 16}}
    write_json(output / "benchmark.json", {"version": 1, "seed": 20261015,
        "suite": "experiments/positions/r2-v1.json", "repeats": 3, "limits": [{"depth": 1}, {"depth": 4}],
        "engines": [entries[1], reference, entries[0]]})
    print(output.resolve())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    prepare(args.baseline, args.candidate, args.output)

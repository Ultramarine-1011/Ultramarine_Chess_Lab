import argparse
import json
from pathlib import Path
from jsonschema import ValidationError

from .match import run_match
from .benchmark import run_benchmark, markdown_benchmark
from .integrity import validate_bundle
from .report import markdown_report


def main():
    parser = argparse.ArgumentParser(description="UCL reproducible experiments")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="UCL repository root")
    commands = parser.add_subparsers(dest="command", required=True)
    match = commands.add_parser("match")
    match.add_argument("--config", type=Path, required=True)
    match.add_argument("--output", type=Path, required=True)
    match.add_argument("--fastchess", default="fastchess")
    match.add_argument("--allow-dirty", action="store_true")
    bench = commands.add_parser("benchmark")
    bench.add_argument("--config", type=Path, required=True)
    bench.add_argument("--output", type=Path, required=True)
    bench.add_argument("--allow-dirty", action="store_true")
    for name in ("validate", "report"):
        sub = commands.add_parser(name)
        sub.add_argument("record", type=Path)
    args = parser.parse_args()
    try:
        if args.command in ("match", "benchmark"):
            record = (run_match(args.root, args.config, args.output, args.fastchess, args.allow_dirty)
                      if args.command == "match" else run_benchmark(args.root, args.config, args.output, args.allow_dirty))
            print(f"{record['status']}: {args.output / 'record.json'}")
            if record["status"] != "completed":
                parser.exit(1, record["error"] + "\n")
        else:
            kind = json.loads(args.record.read_text(encoding="utf-8")).get("kind")
            schema_name = "benchmark-v1.schema.json" if kind == "benchmark" else "experiment-v1.schema.json"
            schema = json.loads((args.root / "schemas" / schema_name).read_text(encoding="utf-8"))
            record = validate_bundle(args.record, schema)
            print("valid experiment bundle (artifacts and recomputed results)" if args.command == "validate" else (markdown_benchmark(record) if kind == "benchmark" else markdown_report(record)))
    except (ValueError, OSError, KeyError, TypeError, ValidationError) as exc:
        parser.exit(1, f"error: {exc}\n")


if __name__ == "__main__":
    main()

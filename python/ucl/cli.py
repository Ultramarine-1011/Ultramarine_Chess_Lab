import argparse
import json
from pathlib import Path
from jsonschema import ValidationError

from .match import run_match
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
    for name in ("validate", "report"):
        sub = commands.add_parser(name)
        sub.add_argument("record", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "match":
            record = run_match(args.root, args.config, args.output, args.fastchess, args.allow_dirty)
            print(f"{record['status']}: {args.output / 'record.json'}")
            if record["status"] != "completed":
                parser.exit(1, record["error"] + "\n")
        else:
            schema = json.loads((args.root / "schemas/experiment-v1.schema.json").read_text(encoding="utf-8"))
            record = validate_bundle(args.record, schema)
            print("valid experiment bundle (hashes, PGN, statistics)" if args.command == "validate" else markdown_report(record))
    except (ValueError, OSError, ValidationError) as exc:
        parser.exit(1, f"error: {exc}\n")


if __name__ == "__main__":
    main()

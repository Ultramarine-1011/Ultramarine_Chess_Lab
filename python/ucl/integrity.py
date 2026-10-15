"""Validate retained evidence without requiring the original host or binaries."""
import json
from pathlib import Path

from .records import sha256, validate_record
from .report import summarize_pgn


def validate_bundle(record_path, schema):
    path = Path(record_path).resolve()
    record = json.loads(path.read_text(encoding="utf-8"))
    validate_record(record, schema)
    from .match import validate_config
    config = record["parameters"]
    validate_config(config)
    if record["seed"] != config["seed"]:
        raise ValueError("record/config seed mismatch")
    for name, expected in record["artifacts"].items():
        artifact = path.parent / name
        if Path(name).name != name or artifact.resolve().parent != path.parent:
            raise ValueError("artifact must be a local bundle file")
        if not artifact.is_file() or artifact.stat().st_size != expected["bytes"] or sha256(artifact) != expected["sha256"]:
            raise ValueError(f"artifact integrity mismatch: {name}")
    # R1 bundles used config.json, which fastchess may have overwritten. Preserve
    # those historical bytes; new bundles always retain match-config.json.
    if "match-config.json" in record["artifacts"]:
        if json.loads((path.parent / "match-config.json").read_text(encoding="utf-8")) != config:
            raise ValueError("saved input configuration mismatch")
    if record["status"] != "completed":
        raise ValueError(f"experiment is {record['status']}, not completed")
    required = {"games.pgn", "fastchess.log"}
    if "openings" in config:
        required.add("openings." + config["openings"]["format"])
    if not required <= record["artifacts"].keys():
        raise ValueError("missing required experiment artifacts")
    for actual, declared in zip(record["engines"], config["engines"], strict=True):
        for key in ("name", "options", "build"):
            if actual[key] != declared[key]:
                raise ValueError(f"engine {key} mismatch")
        revision = record["code"]["revision"] if declared["revision"] == "HEAD" else declared["revision"]
        if actual["revision"] != revision:
            raise ValueError("engine revision mismatch")
        info = actual.get("build_info")
        if declared.get("ucl_build_info") and (not info or info["revision"] != revision):
            raise ValueError("binary build provenance mismatch")
    a, b = config["engines"]
    results = summarize_pgn(path.parent / "games.pgn", a["name"], b["name"],
                            config["rounds"] * config["games"], record["seed"])
    # Accept R1 records predating optional paired_score_counts, while checking
    # every statistic they actually retained.
    if record["results"] != {k: results[k] for k in record["results"]}:
        raise ValueError("PGN/statistics mismatch")
    if results["paired_rounds"] != config["rounds"] or any(
            reason not in ("normal", "adjudication") for reason in results["terminations"]):
        raise ValueError("invalid pairs or abnormal termination")
    return record

"""Validate retained evidence without requiring the original host or binaries."""
import json
from pathlib import Path

from .records import sha256, validate_record
from .report import summarize_pgn


def validate_bundle(record_path, schema, completed_prefix_games=None):
    path = Path(record_path).resolve()
    record = json.loads(path.read_text(encoding="utf-8"))
    validate_record(record, schema)
    for name, expected in record["artifacts"].items():
        artifact = path.parent / name
        if Path(name).name != name or artifact.resolve().parent != path.parent:
            raise ValueError("artifact must be a local bundle file")
        if not artifact.is_file() or artifact.stat().st_size != expected["bytes"] or sha256(artifact) != expected["sha256"]:
            raise ValueError(f"artifact integrity mismatch: {name}")
    if record["kind"] == "benchmark":
        from .benchmark import validate_benchmark_bundle
        return validate_benchmark_bundle(path, record)
    from .match import validate_config, validate_comparison, validate_evaluation, validate_telemetry, validate_external_identity, validate_match_warnings
    config = record["parameters"]
    validate_config(config)
    if record["seed"] != config["seed"]:
        raise ValueError("record/config seed mismatch")
    if not {"match-config.json", "config.json"} & record["artifacts"].keys():
        raise ValueError("missing saved configuration")
    # R1 bundles used config.json, which fastchess may have overwritten. Preserve
    # those historical bytes; new bundles always retain match-config.json.
    if "match-config.json" in record["artifacts"]:
        if json.loads((path.parent / "match-config.json").read_text(encoding="utf-8")) != config:
            raise ValueError("saved input configuration mismatch")
    prefix = completed_prefix_games is not None
    if prefix:
        if (record['status']!='failed' or type(completed_prefix_games) is not int or completed_prefix_games<2
                or completed_prefix_games%2 or completed_prefix_games>=config['rounds']*config['games']):
            raise ValueError('invalid completed-prefix request')
    elif record["status"] != "completed":
        raise ValueError(f"experiment is {record['status']}, not completed")
    required = {"games.pgn", "fastchess.log"}
    if "openings" in config:
        required.add("openings." + config["openings"]["format"])
    if not required <= record["artifacts"].keys():
        raise ValueError("missing required experiment artifacts")
    validate_telemetry(record, path.parent)
    validate_match_warnings(config, path.parent / "fastchess.log")
    for actual, declared in zip(record["engines"], config["engines"], strict=True):
        validate_external_identity(actual, declared)
        validate_evaluation(actual, path.parent, record["artifacts"])
        for key in ("name", "options", "build"):
            if actual[key] != declared[key]:
                raise ValueError(f"engine {key} mismatch")
        revision = record["code"]["revision"] if declared["revision"] == "HEAD" else declared["revision"]
        formal = record.get('mode', 'formal') == 'formal'
        captured_revision = actual['build_info']['revision'] if actual.get('build_info') else revision
        if actual["revision"] != captured_revision or (formal and actual["revision"] != revision):
            raise ValueError("engine revision mismatch")
        info = actual.get("build_info")
        if formal and declared.get("ucl_build_info") and (not info or info["revision"] != revision):
            raise ValueError("binary build provenance mismatch")
    if record.get('mode', 'formal') == 'formal':
        validate_comparison(config, record["engines"])
    a, b = config["engines"]
    results = summarize_pgn(path.parent / "games.pgn", a["name"], b["name"],
                            completed_prefix_games if prefix else config["rounds"] * config["games"], record["seed"])
    # Accept R1 records predating optional paired_score_counts, while checking
    # every statistic they actually retained.
    if not prefix and record["results"] != {k: results[k] for k in record["results"]}:
        raise ValueError("PGN/statistics mismatch")
    expected_rounds=completed_prefix_games//2 if prefix else config['rounds']
    if results["paired_rounds"] != expected_rounds or any(
            reason not in ("normal", "adjudication") for reason in results["terminations"]):
        raise ValueError("invalid pairs or abnormal termination")
    if prefix:
        # The original failed record stays failed and is never rewritten. This
        # explicit opt-in only validates complete paired PGNs for fixed-plan recovery.
        record['tools']['completed_prefix']={'games':completed_prefix_games,'results':results,
            'source_status':record['status'],'source_error':record['error'],'source_record_sha256':sha256(path)}
    return record

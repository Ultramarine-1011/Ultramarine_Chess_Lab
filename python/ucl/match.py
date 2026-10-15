"""Run a pinned external fastchess, retaining metadata even on failure."""
import json
import os
from pathlib import Path
import re
import signal
import shutil
import subprocess

from .records import new_record, sha256, utc_now, validate_record, write_json
from .report import markdown_report, summarize_pgn


def executable(value, root):
    local = (root / value).resolve()
    found = str(local) if local.is_file() else shutil.which(value)
    if not found:
        raise FileNotFoundError(f"executable not found: {value}")
    return Path(found).resolve()


def validate_config(c):
    required = {"version", "seed", "engines", "rounds", "games", "concurrency", "tc", "maxmoves", "timeout_seconds"}
    if not required <= c.keys() or c.keys() - required - {"depth", "nodes", "openings", "comparison"}:
        raise ValueError("missing or unknown match configuration fields")
    if c["version"] != 1 or len(c["engines"]) != 2 or c["games"] != 2:
        raise ValueError("version 1 requires two engines and color-swapped game pairs")
    for key in ("rounds", "concurrency", "maxmoves", "timeout_seconds", "depth", "nodes"):
        if key in c and (type(c[key]) is not int or c[key] <= 0):
            raise ValueError(f"{key} must be a positive integer")
    if type(c["seed"]) is not int or not 0 <= c["seed"] <= 2147483647:
        raise ValueError("seed must be a nonnegative 31-bit integer")
    if not isinstance(c["tc"], str) or not c["tc"]:
        raise ValueError("tc must be a fastchess time-control string")
    if c.get("comparison", "smoke") not in ("smoke", "ablation", "revision"):
        raise ValueError("comparison must be smoke/ablation/revision")
    names = []
    for e in c["engines"]:
        if not {"name", "path", "revision", "build", "options"} <= e.keys() or e.keys() - {"name", "path", "revision", "build", "options", "ucl_build_info"} or not all(isinstance(e[k], str) and e[k] for k in ("name", "path", "revision", "build")):
            raise ValueError("engine requires name/path/revision/build/options")
        if e["revision"] != "HEAD" and not re.fullmatch(r"[0-9a-f]{40}", e["revision"]):
            raise ValueError("engine revision must be a full commit SHA or HEAD")
        if type(e.get("ucl_build_info", False)) is not bool:
            raise ValueError("ucl_build_info must be boolean")
        if not isinstance(e["options"], dict) or not all(isinstance(k, str) and isinstance(v, (str, int, float, bool)) for k, v in e["options"].items()):
            raise ValueError("options must be a scalar mapping")
        names.append(e["name"])
    if len(set(names)) != 2:
        raise ValueError("engine names must differ")
    if "openings" in c:
        o = c["openings"]
        if set(o) != {"path", "format", "order"} or o["format"] not in ("epd", "pgn") or o["order"] not in ("random", "sequential"):
            raise ValueError("invalid openings configuration")


def command(config, paths, fastchess, pgn, opening=None):
    args = [str(fastchess)]
    for e, path in zip(config["engines"], paths, strict=True):
        args += ["-engine", f"cmd={path}", f"name={e['name']}", "proto=uci"]
        args += [f"option.{k}={str(v).lower() if isinstance(v, bool) else v}" for k, v in sorted(e["options"].items())]
    args += ["-each", f"tc={config['tc']}"]
    for field in ("depth", "nodes"):
        if field in config:
            args.append(f"{field}={config[field]}")
    for field in ("rounds", "games", "concurrency", "maxmoves"):
        args += [f"-{field}", str(config[field])]
    args += ["-srand", str(config["seed"]), "-pgnout", f"file={pgn}", "append=false",
             "-autosaveinterval", "0", "-strict"]
    if opening:
        args += ["-openings", f"file={opening}", f"format={config['openings']['format']}", f"order={config['openings']['order']}"]
    return args


def run_process(args, output, log, timeout):
    """Kill the process tree on timeout/interrupt so engines cannot leak CPU jobs."""
    kwargs = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {"start_new_session": True}
    with subprocess.Popen(args, cwd=output, stdout=log, stderr=subprocess.STDOUT, text=True, **kwargs) as process:
        try:
            return process.wait(timeout=timeout)
        except (subprocess.TimeoutExpired, KeyboardInterrupt):
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], stdout=log, stderr=subprocess.STDOUT, check=False)
            else:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            process.wait()
            raise


def run_match(root, config_path, output, fastchess="fastchess", allow_dirty=False):
    root, output = Path(root).resolve(), Path(output).resolve()
    config = json.loads(Path(config_path).read_text(encoding="utf-8"))
    validate_config(config)
    record = new_record(root, config)
    if record["code"]["dirty"] and not allow_dirty:
        raise ValueError("working tree is dirty; commit first or explicitly pass --allow-dirty for diagnostics")
    schema = json.loads((root / "schemas/experiment-v1.schema.json").read_text(encoding="utf-8"))
    # Refuse to overwrite earlier experiment evidence.
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / "match-config.json", config)
    paths = []
    try:
        fast = executable(fastchess, root)
        record["tools"]["fastchess"] = {"path": str(fast), "sha256": sha256(fast),
            "version": subprocess.check_output([str(fast), "--version"], text=True, timeout=10).strip()}
        for e in config["engines"]:
            entry = capture_engine(root, e, record["code"]["revision"], allow_dirty)
            paths.append(Path(entry["path"]))
            record["engines"].append(entry)
        validate_comparison(config, record["engines"])
        opening = None
        if "openings" in config:
            original = (root / config["openings"]["path"]).resolve()
            opening = output / ("openings." + config["openings"]["format"])
            shutil.copyfile(original, opening)
        args = command(config, paths, fast, output / "games.pgn", opening)
        record["tools"]["command"] = args
        validate_record(record, schema)
        write_json(output / "record.json", record)
        with (output / "fastchess.log").open("w", encoding="utf-8") as log:
            returncode = run_process(args, output, log, config["timeout_seconds"])
        if returncode:
            raise RuntimeError(f"fastchess exited {returncode}; see fastchess.log")
        e1, e2 = config["engines"]
        record["results"] = summarize_pgn(output / "games.pgn", e1["name"], e2["name"],
            config["rounds"] * config["games"], config["seed"])
        if record["results"]["paired_rounds"] != config["rounds"]:
            raise ValueError("PGN does not contain the expected color-swapped pairs")
        if any(reason not in ("normal", "adjudication") for reason in record["results"]["terminations"]):
            raise ValueError("abnormal game termination; inspect PGN and log")
        record["status"] = "completed"
    except (Exception, KeyboardInterrupt) as exc:
        record["status"], record["error"] = "failed", f"{type(exc).__name__}: {exc}"
    finally:
        record["finished_at"] = utc_now()
        for path in output.iterdir():
            if path.is_file() and path.name not in ("record.json", "report.md"):
                record["artifacts"][path.name] = {"sha256": sha256(path), "bytes": path.stat().st_size}
        validate_record(record, schema)
        write_json(output / "record.json", record)
        (output / "report.md").write_text(markdown_report(record), encoding="utf-8")
    return record


def validate_comparison(config, engines):
    kind = config.get("comparison", "smoke")
    a, b = engines
    if kind == "revision":
        if a["sha256"] == b["sha256"] or a["revision"] == b["revision"]:
            raise ValueError("revision comparison requires distinct binary hashes and Git revisions")
        if any(not e.get("build_info") or e["build_info"]["dirty"] for e in engines):
            raise ValueError("revision comparison requires clean UCL --build-info provenance")
        for key in ("compiler", "build_type", "flags"):
            if a["build_info"][key] != b["build_info"][key]:
                raise ValueError(f"revision comparison build control differs: {key}")
    if kind == "ablation" and (a["sha256"] != b["sha256"] or a["options"] == b["options"]):
        raise ValueError("ablation requires the same binary with different explicit options")


def capture_engine(root, e, code_revision, allow_dirty=False):
    path = executable(e["path"], Path(root))
    entry = {k: v for k, v in e.items() if k != "ucl_build_info"}
    entry.update(path=str(path), sha256=sha256(path),
                 revision=code_revision if e["revision"] == "HEAD" else e["revision"], build_info=None)
    if e.get("ucl_build_info"):
        info = json.loads(subprocess.check_output([str(path), "--build-info"], text=True, timeout=10))
        entry["build_info"] = info
        if info["revision"] != entry["revision"] or (info["dirty"] and not allow_dirty):
            raise ValueError("UCL binary revision/dirty state mismatch: reconfigure and rebuild after committing")
    return entry

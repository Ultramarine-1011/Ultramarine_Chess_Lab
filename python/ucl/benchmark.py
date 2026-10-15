"""Single-thread deterministic search controls, retained UCI transcripts and medians."""
import json
import logging
from pathlib import Path
import random
import statistics
import time

import chess
import chess.engine

from .match import capture_engine, validate_engine, runtime_options, validate_evaluation
from .records import new_record, prepare_output, sha256, utc_now, write_json


def validate_config_benchmark(c):
    required = {"version", "seed", "suite", "repeats", "limits", "engines"}
    if not required <= c.keys() or c.keys() - required - {"static_evaluation"} or c["version"] != 1:
        raise ValueError("invalid benchmark configuration")
    if "static_evaluation" in c and type(c["static_evaluation"]) is not bool:
        raise ValueError("static_evaluation must be boolean")
    if type(c["repeats"]) is not int or not 1 <= c["repeats"] <= 100:
        raise ValueError("repeats must be 1..100")
    if not c["limits"] or any(set(l) not in ({"depth"}, {"nodes"}) or any(type(v) is not int or v < 1 for v in l.values()) or l.get("depth", 1) > 128 for l in c["limits"]):
        raise ValueError("limits must be positive depth (<=128) or nodes")
    if len({json.dumps(l, sort_keys=True) for l in c["limits"]}) != len(c["limits"]):
        raise ValueError("duplicate benchmark limits")
    if len(c["engines"]) < 1 or len({e["name"] for e in c["engines"]}) != len(c["engines"]):
        raise ValueError("benchmark engine names must be unique")
    if type(c['seed']) is not int or not 0 <= c['seed'] <= 2147483647:
        raise ValueError('seed must be a nonnegative 31-bit integer')
    for e in c["engines"]:
        validate_engine(e)


def load_suite(path):
    suite = json.loads(Path(path).read_text(encoding="utf-8"))
    if suite["version"] != 1 or not suite["positions"]:
        raise ValueError("invalid position suite")
    ids = []
    for case in suite["positions"]:
        ids.append(case["id"])
        board = chess.Board(case["fen"])
        if not board.is_valid():
            raise ValueError(f"illegal suite position: {case['id']}")
        for move in case.get("best", []) + case.get("avoid", []):
            if chess.Move.from_uci(move) not in board.legal_moves:
                raise ValueError("illegal tactical label")
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate position ids")
    return suite


def uci_score_cp(score):
    """Restore UCL's root-relative ply distance from UCI mate-in-moves.

    Positive mate N is 2*N-1 plies; negative mate -N is 2*N plies.
    python-chess's generic score(mate_score=...) uses N directly instead.
    """
    mate = score.mate()
    if mate is None:
        return score.score()
    if mate == 0:
        return 30000 if score > chess.engine.Cp(0) else -30000
    return 30000 - (2 * mate - 1) if mate > 0 else -30000 - 2 * mate


def tactical_pass(case, move, score):
    checks = []
    if "best" in case:
        checks.append(move in case["best"])
    if "avoid" in case:
        checks.append(move not in case["avoid"])
    if "score_cp" in case:
        checks.append(score == case["score_cp"])
    if "mate_plies" in case:
        board = chess.Board(case["fen"])
        if move:
            board.push_uci(move)
        checks.append(board.is_checkmate() and score == 30000 - case["mate_plies"])
    return all(checks) if checks else None


def summarize(rows):
    groups = {}
    for row in rows:
        key = (row["engine"], json.dumps(row["limit"], sort_keys=True))
        groups.setdefault(key, []).append(row)
    summary = []
    for (engine, limit), data in sorted(groups.items()):
        # Sum per-position medians to avoid the arbitrary order/thermal effects of
        # selecting a single run. NPS is throughput, not strength.
        positions = {}
        for row in data:
            positions.setdefault(row["position"], []).append(row)
        nodes = sum(statistics.median(r["nodes"] for r in group) for group in positions.values())
        elapsed = sum(statistics.median(r["wall_ns"] for r in group) for group in positions.values())
        labels = [g for g in positions.values() if g[0]["tactical_pass"] is not None]
        summary.append({"engine": engine, "limit": json.loads(limit), "positions": len(positions),
            "median_nodes_sum": nodes, "median_wall_ms_sum": elapsed / 1e6,
            "wall_nps": nodes * 1e9 / max(1, elapsed),
            "tactical_passes": sum(all(r["tactical_pass"] for r in group) for group in labels),
            "tactical_total": len(labels),
            "depth_min": min(r["depth"] for r in data), "depth_max": max(r["depth"] for r in data),
            "tt_hits_sum": sum(r["tt_hits"] or 0 for r in data),
            "tt_cutoffs_sum": sum(r["tt_cutoffs"] or 0 for r in data)})
    return summary


def markdown_benchmark(record):
    lines = ["# UCL search benchmark", "", f"Mode: {record.get('mode', 'historical')}; revision: `{record['code']['revision']}`; dirty: {record['code']['dirty']}", "",
             "Per-position medians; wall time includes UCI round trip and TT allocation. Single search thread; cold TT per query.", "",
             "| Engine | Limit | Nodes | Wall ms | Wall NPS | Tactical checks |", "|---|---|---:|---:|---:|---:|"]
    for row in record["summary"]:
        lines.append(f"| {row['engine']} | {row['limit']} | {row['median_nodes_sum']:g} | {row['median_wall_ms_sum']:.2f} | {row['wall_nps']:.0f} | {row['tactical_passes']}/{row['tactical_total']} |")
    if 'static_evaluation' in record['tools']:
        static = record['tools']['static_evaluation']['summary']
        lines += ['', 'Static evaluation: mean of per-position median ns/call (7 alternating repeats, 100000 calls/model/position):',
                  f"Handcrafted {static['mean_position_median_handcrafted_ns']:.2f} ns; Linear {static['mean_position_median_linear_ns']:.2f} ns.",
                  'Raw static measurements and checksums are retained separately; repeated timings are descriptive, not a significance test.']
    lines += ["", "QS changes leaf semantics. Tactical labels are narrow regression checks; this suite and throughput do not measure Elo.",
              "R1 lacks final interrupted-search counters; its node-limited totals are last completed iteration only. Compare R1 at fixed depth.", ""]
    return "\n".join(lines)


def run_benchmark(root, config_path, output, *, formal=False, overwrite=False):
    root, output = Path(root).resolve(), Path(output).resolve()
    config = json.loads(Path(config_path).read_text(encoding="utf-8"))
    validate_config_benchmark(config)
    suite_path = (root / config["suite"]).resolve()
    suite = load_suite(suite_path)
    if formal and overwrite:
        raise ValueError('formal runs cannot overwrite evidence')
    record = new_record(root, config, formal)
    record.update(kind="benchmark", rows=[], summary=[])
    record.pop("results")
    prepare_output(root, output, overwrite)
    write_json(output / "benchmark-config.json", config)
    write_json(output / "positions.json", suite)
    logger = logging.getLogger("chess.engine")
    handler = logging.FileHandler(output / "uci.log", encoding="utf-8")
    old_level = logger.level
    logger.addHandler(handler); logger.setLevel(logging.DEBUG)
    clients = {}
    try:
        for e in config["engines"]:
            entry = capture_engine(root, e, record["code"]["revision"], formal=formal)
            record["engines"].append(entry)
            client = chess.engine.SimpleEngine.popen_uci(entry["path"], timeout=30)
            clients[e["name"]] = client
            client.configure(runtime_options(root, e["options"], output))
        rng = random.Random(config["seed"])
        for repeat in range(config["repeats"]):
            for case in suite["positions"]:
                names = list(clients)
                rng.shuffle(names) # Fixed order seed, alternate configurations across repetitions.
                for limit in config["limits"]:
                    for name in names:
                        board = chess.Board(case["fen"])
                        before = time.perf_counter_ns()
                        played = clients[name].play(board, chess.engine.Limit(**limit), game=object(), info=chess.engine.INFO_ALL)
                        info = played.info
                        wall = time.perf_counter_ns() - before
                        text = info.get("string", "")
                        native = json.loads(text.removeprefix("ucl_stats ")) if text.startswith("ucl_stats ") else None
                        pv = [m.uci() for m in info.get("pv", [])]
                        for move in pv:
                            board.push_uci(move) # Independent legal validation.
                        score = native["score_cp"] if native else (uci_score_cp(info["score"].relative) if "score" in info else (-30000 if board.is_checkmate() else 0))
                        row = {"engine": name, "position": case["id"], "repeat": repeat, "limit": limit,
                               "depth": native["depth"] if native else info.get("depth", 0),
                               "score_cp": score, "pv": pv, "move": played.move.uci() if played.move else None,
                               "nodes": native["nodes"] if native else info.get("nodes", 0), "wall_ns": wall,
                               "elapsed_us": native["elapsed_us"] if native else round(info.get("time", 0) * 1e6),
                               "counter_scope": "final" if native else "last_completed_iteration"}
                        for key in ("qnodes", "tt_probes", "tt_hits", "tt_cutoffs", "tt_stores", "pv_order_hits", "tt_order_hits"):
                            row[key] = native[key] if native else None
                        row["nps"] = row["nodes"] * 1e6 / max(1, row["elapsed_us"])
                        row["tactical_pass"] = tactical_pass(case, row["move"], score)
                        record["rows"].append(row)
        record["summary"] = summarize(record["rows"])
        if config.get("static_evaluation"):
            linear = [e for e in record["engines"] if e["options"].get("Evaluator") == "Linear"]
            if len(linear) != 1:
                raise ValueError("static evaluation requires exactly one linear evaluator")
            record["tools"]["static_evaluation"] = run_static_evaluation(linear[0], runtime_options(root, linear[0]["options"], output), suite, output)
        record["status"] = "completed"
    except (Exception, KeyboardInterrupt) as exc:
        record["status"], record["error"] = "failed", f"{type(exc).__name__}: {exc}"
    finally:
        for client in clients.values():
            try:
                client.quit()
            except (chess.engine.EngineError, TimeoutError):
                client.close()
        logger.removeHandler(handler); handler.close(); logger.setLevel(old_level)
        record["finished_at"] = utc_now()
        for artifact in output.iterdir():
            if artifact.is_file():
                record["artifacts"][artifact.name] = {"sha256": sha256(artifact), "bytes": artifact.stat().st_size}
        write_json(output / "record.json", record)
        (output / "report.md").write_text(markdown_benchmark(record), encoding="utf-8")
    return record


def validate_benchmark_bundle(path, record):
    config = record["parameters"]
    validate_config_benchmark(config)
    if record["status"] != "completed" or record["seed"] != config["seed"]:
        raise ValueError("incomplete benchmark or seed mismatch")
    required = {"benchmark-config.json", "positions.json", "uci.log"}
    if not required <= record["artifacts"].keys():
        raise ValueError("missing benchmark artifacts")
    if json.loads((path.parent / "benchmark-config.json").read_text()) != config:
        raise ValueError("benchmark config mismatch")
    if 'measurements.json' in record['artifacts'] and json.loads((path.parent / "measurements.json").read_text()) != record["rows"]:
        raise ValueError("benchmark measurement mismatch")
    cases = {c["id"]: c for c in load_suite(path.parent / "positions.json")["positions"]}
    engines = {e["name"]: e for e in record["engines"]}
    if set(engines) != {e["name"] for e in config["engines"]}:
        raise ValueError("benchmark engine names mismatch")
    for declared in config["engines"]:
        actual = engines[declared["name"]]
        validate_evaluation(actual, path.parent, record["artifacts"])
        revision = record["code"]["revision"] if declared["revision"] == "HEAD" else declared["revision"]
        formal = record.get('mode', 'formal') == 'formal'
        captured_revision = actual['build_info']['revision'] if actual.get('build_info') else revision
        if any(actual[k] != declared[k] for k in ("name", "options", "build")) or actual['revision'] != captured_revision or (formal and actual["revision"] != revision):
            raise ValueError("benchmark engine declaration mismatch")
        if formal and declared.get("ucl_build_info") and (not actual.get("build_info") or actual["build_info"]["revision"] != revision):
            raise ValueError("benchmark binary provenance mismatch")
    if config.get("static_evaluation"):
        validate_static(record, path, cases)
    seen = set()
    for row in record["rows"]:
        identity = (row["engine"], row["position"], row["repeat"], json.dumps(row["limit"], sort_keys=True))
        if identity in seen or row["engine"] not in engines or row["position"] not in cases or not 0 <= row["repeat"] < config["repeats"] or row["limit"] not in config["limits"]:
            raise ValueError("duplicate or invalid measurement identity")
        seen.add(identity)
        case = cases[row["position"]]
        board = chess.Board(case["fen"])
        move = row["move"]
        if move is not None and chess.Move.from_uci(move) not in board.legal_moves:
            raise ValueError("illegal benchmark move")
        if move is None and not board.is_game_over(claim_draw=True):
            raise ValueError("missing benchmark move")
        for m in row["pv"]:
            parsed = chess.Move.from_uci(m)
            if parsed not in board.legal_moves:
                raise ValueError("illegal benchmark PV")
            board.push(parsed)
        if row["pv"] and row["pv"][0] != move:
            raise ValueError("PV/bestmove mismatch")
        if row["tactical_pass"] != tactical_pass(case, move, row["score_cp"]):
            raise ValueError("tactical summary mismatch")
        if row["nps"] != row["nodes"] * 1e6 / max(1, row["elapsed_us"]):
            raise ValueError("NPS mismatch")
        if "nodes" in row["limit"] and row["nodes"] > row["limit"]["nodes"]:
            raise ValueError("node limit exceeded")
        if row["depth"] > row["limit"].get("depth", 128):
            raise ValueError("depth limit exceeded")
        if row["counter_scope"] == "final":
            if not 0 <= row["qnodes"] <= row["nodes"] or not 0 <= row["tt_cutoffs"] <= row["tt_hits"] <= row["tt_probes"] <= row["nodes"]:
                raise ValueError("inconsistent search counters")
        elif row["counter_scope"] != "last_completed_iteration":
            raise ValueError("unknown counter scope")
    expected = len(engines) * len(cases) * config["repeats"] * len(config["limits"])
    if len(seen) != expected or record["summary"] != summarize(record["rows"]):
        raise ValueError("benchmark coverage/summary mismatch")
    return record


def summarize_static(rows):
    groups = {}
    for r in rows:
        groups.setdefault(r['position'], []).append(r)
    positions = []
    for name, group in groups.items():
        positions.append({'position': name, **{kind+'_ns_per_call': statistics.median(
            r[kind+'_ns']/r['iterations'] for r in group) for kind in ('handcrafted', 'linear')}})
    return {'positions': positions,
            'mean_position_median_handcrafted_ns': statistics.mean(p['handcrafted_ns_per_call'] for p in positions),
            'mean_position_median_linear_ns': statistics.mean(p['linear_ns_per_call'] for p in positions)}


def run_static_evaluation(entry, options, suite, output):
    import subprocess
    args = [entry['path'], '--eval-benchmark', options['ModelFile'], options['ModelSHA256']]
    result = subprocess.run(args, input='\n'.join(p['fen'] for p in suite['positions'])+'\n',
                            capture_output=True, text=True, check=True, timeout=60)
    raw = [json.loads(line) for line in result.stdout.splitlines()]
    if len(raw) != len(suite['positions'])*7:
        raise ValueError('static evaluation row count mismatch')
    rows = [{**r, 'position': suite['positions'][i//7]['id']} for i,r in enumerate(raw)]
    write_json(output/'static-evaluation.json', rows)
    return {'command': args, 'summary': summarize_static(rows)}


def validate_static(record, path, cases):
    import math
    from .feature_data import reference_features, WEIGHTS
    from .model import load_model
    static = record['tools'].get('static_evaluation')
    if not static or 'static-evaluation.json' not in record['artifacts']:
        raise ValueError('missing static evaluation evidence')
    linear = [e for e in record['engines'] if e['options'].get('Evaluator') == 'Linear']
    if len(linear) != 1:
        raise ValueError('static evaluation requires one linear evaluator')
    model_hash = linear[0]['evaluation']['model_sha256']
    weights = load_model(path.parent/('model-'+model_hash+'.txt'), model_hash)
    rows = json.loads((path.parent/'static-evaluation.json').read_text())
    seen = set()
    for r in rows:
        if set(r) != {'position','repeat','iterations','handcrafted_ns','linear_ns','checksum','model_sha256'}:
            raise ValueError('static evaluation schema mismatch')
        key = r['position'], r['repeat']
        if key in seen or key[0] not in cases or type(key[1]) is not int or not 0 <= key[1] < 7:
            raise ValueError('static evaluation identity mismatch')
        seen.add(key)
        if r['iterations'] != 100000 or r['model_sha256'] != model_hash or any(type(r[k]) is not int or r[k] <= 0 for k in ('handcrafted_ns','linear_ns')):
            raise ValueError('invalid static evaluation measurement')
        b = chess.Board(cases[key[0]]['fen'])
        if len(weights) == 14:
            from .r4_features import reference
            x = reference(b)
        else:
            x = reference_features(b)
        def score(w):
            s = sum(a*v for a,v in zip(w,x))
            return math.floor(abs(s)+.5)*(1 if s>=0 else -1)*(1 if b.turn else -1)
        if r['checksum'] != (score(WEIGHTS)+score(weights))*100000:
            raise ValueError('static evaluation checksum mismatch')
    if len(rows) != len(cases)*7 or static['summary'] != summarize_static(rows):
        raise ValueError('static evaluation coverage/summary mismatch')

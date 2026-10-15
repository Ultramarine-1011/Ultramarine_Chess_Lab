"""Run a pinned external fastchess, retaining metadata even on failure."""
import json
import gzip
import hashlib
import os
from pathlib import Path
import re
import signal
import shutil
import subprocess

from .records import new_record, prepare_output, sha256, utc_now, write_json
from .report import markdown_report, summarize_pgn


def executable(value, root):
    local = (root / value).resolve()
    found = str(local) if local.is_file() else shutil.which(value)
    if not found:
        raise FileNotFoundError(f"executable not found: {value}")
    return Path(found).resolve()


def validate_config(c):
    required = {"version", "seed", "engines", "rounds", "games", "concurrency", "tc", "maxmoves", "timeout_seconds"}
    if not required <= c.keys() or c.keys() - required - {"depth", "nodes", "openings", "comparison", "pgn_telemetry"}:
        raise ValueError("missing or unknown match configuration fields")
    if 'pgn_telemetry' in c and type(c['pgn_telemetry']) is not bool:
        raise ValueError('pgn_telemetry must be boolean')
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
        validate_engine(e)
        names.append(e["name"])
    if len(set(names)) != 2:
        raise ValueError("engine names must differ")
    if "openings" in c:
        o = c["openings"]
        if set(o) != {"path", "format", "order"} or o["format"] not in ("epd", "pgn") or o["order"] not in ("random", "sequential"):
            raise ValueError("invalid openings configuration")


def validate_engine(e):
    if not {"name", "path", "revision", "build", "options"} <= e.keys() or not all(
            isinstance(e[k], str) and e[k] for k in ("name", "path", "revision", "build")):
        raise ValueError("engine requires name/path/revision/build/options")
    if e["revision"] != "HEAD" and not re.fullmatch(r"[0-9a-f]{40}", e["revision"]):
        raise ValueError("engine revision must be a full commit SHA or HEAD")
    if not isinstance(e["options"], dict) or not all(isinstance(k, str) and isinstance(v, (str, int, float, bool)) for k, v in e["options"].items()):
        raise ValueError("options must be a scalar mapping")


def command(config, paths, fastchess, pgn, opening=None, engine_options=None):
    args = [str(fastchess)]
    for index, (e, path) in enumerate(zip(config["engines"], paths, strict=True)):
        args += ["-engine", f"cmd={path}", f"name={e['name']}", "proto=uci"]
        args += [f"option.{k}={str(v).lower() if isinstance(v, bool) else v}" for k, v in ordered_options(e["options"] if engine_options is None else engine_options[index]).items()]
    args += ["-each", f"tc={config['tc']}"]
    for field in ("depth", "nodes"):
        if field in config:
            args.append(f"{field}={config[field]}")
    for field in ("rounds", "games", "concurrency", "maxmoves"):
        args += [f"-{field}", str(config[field])]
    args += ["-srand", str(config["seed"]), "-pgnout", f"file={pgn}", "append=false"]
    if config.get('pgn_telemetry'):
        args += ['nodes=true','nps=true','timeleft=true','latency=true',
                 '-log',f'file={Path(pgn).parent / "engine.log"}','level=trace','engine=true','append=false','compress=false']
    args += ["-autosaveinterval", "0", "-strict"]
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


def run_match(root, config_path, output, fastchess="fastchess", *, formal=False, overwrite=False):
    root, output = Path(root).resolve(), Path(output).resolve()
    config = json.loads(Path(config_path).read_text(encoding="utf-8"))
    validate_config(config)
    if formal and overwrite:
        raise ValueError('formal runs cannot overwrite evidence')
    record = new_record(root, config, formal)
    prepare_output(root, output, overwrite)
    write_json(output / "match-config.json", config)
    paths = []
    try:
        fast = executable(fastchess, root)
        record["tools"]["fastchess"] = {"path": str(fast), "sha256": sha256(fast),
            "version": subprocess.check_output([str(fast), "--version"], text=True, timeout=10).strip()}
        for e in config["engines"]:
            entry = capture_engine(root, e, record["code"]["revision"], formal=formal)
            paths.append(Path(entry["path"]))
            record["engines"].append(entry)
        if formal:
            validate_comparison(config, record["engines"])
        opening = None
        if "openings" in config:
            original = (root / config["openings"]["path"]).resolve()
            opening = output / ("openings." + config["openings"]["format"])
            shutil.copyfile(original, opening)
        runtime = [runtime_options(root, e["options"], output) for e in config["engines"]]
        args = command(config, paths, fast, output / "games.pgn", opening, runtime)
        record["tools"]["command"] = args
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
        if config.get('pgn_telemetry') and (output/'engine.log').exists():
            original=output/'engine.log'
            record['tools']['telemetry']={'file':'engine.log.gz'}
            with original.open('rb') as source, (output/'engine.log.gz').open('wb') as target:
                with gzip.GzipFile(filename='',mode='wb',fileobj=target,mtime=0) as compressed:
                    shutil.copyfileobj(source,compressed)
            original.unlink() # Exact raw bytes are retained reversibly in gzip.
        for path in output.iterdir():
            if path.is_file() and path.name not in ("record.json", "report.md"):
                record["artifacts"][path.name] = {"sha256": sha256(path), "bytes": path.stat().st_size}
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


def capture_engine(root, e, code_revision, *, formal=False):
    path = executable(e["path"], Path(root))
    entry = {k: v for k, v in e.items() if k != "ucl_build_info"}
    entry.update(path=str(path), sha256=sha256(path),
                 revision=code_revision if e["revision"] == "HEAD" else e["revision"], build_info=None)
    if e.get("ucl_build_info"):
        info = json.loads(subprocess.check_output([str(path), "--build-info"], text=True, timeout=10))
        entry["build_info"] = info
        if formal and (info["revision"] != entry["revision"] or info["dirty"]):
            raise ValueError("formal comparison needs a clean binary of the declared revision")
        entry['revision'] = info['revision']
    if 'Evaluator' in e['options']:
        options = runtime_options(root, e['options'])
        lines = ['uci'] + ['setoption name '+k+' value '+(str(v).lower() if isinstance(v,bool) else str(v)) for k,v in options.items()]
        lines += ['evalinfo','quit']
        response = subprocess.run([str(path)], input='\n'.join(lines)+'\n', capture_output=True, text=True, timeout=10, check=True)
        if 'command rejected' in response.stdout or 'unsupported option' in response.stdout:
            raise ValueError('engine rejected evaluator configuration')
        identities = [json.loads(line.removeprefix('info string ucl_evaluator ')) for line in response.stdout.splitlines() if line.startswith('info string ucl_evaluator ')]
        if len(identities) != 1:
            raise ValueError('missing actual evaluator identity')
        entry['evaluation'] = identities[0]
        expected = model_identity(options['ModelFile'], options['ModelSHA256']) if e['options']['Evaluator'] == 'Linear' else 'handcrafted-v1'
        if entry['evaluation'] != {'evaluator': expected, 'model_sha256': e['options'].get('ModelSHA256') if expected.startswith('linear-') else None}:
            raise ValueError('engine evaluator/model identity mismatch')
    return entry


def ordered_options(options):
    """Hash and file must load successfully before selecting Linear."""
    priority = {'ModelSHA256': 0, 'ModelFile': 1, 'Evaluator': 2}
    return dict(sorted(options.items(), key=lambda kv: (priority.get(kv[0], 3), kv[0])))


def runtime_options(root, options, output=None):
    options = ordered_options(options)
    if options.get('Evaluator') == 'Linear' or 'ModelFile' in options:
        if not {'ModelFile', 'ModelSHA256'} <= options.keys():
            raise ValueError('Linear requires explicit ModelFile and ModelSHA256')
        model = (Path(root)/options['ModelFile']).resolve()
        if output is not None:
            target = Path(output)/('model-'+options['ModelSHA256']+'.txt')
            if not target.exists():
                shutil.copyfile(model, target)
            model = target.resolve()
        options['ModelFile'] = str(model)
    return options


def validate_evaluation(entry, directory, artifacts):
    """Retained metadata must identify what the configured engine actually used."""
    options = entry['options']
    if 'Evaluator' not in options:
        return # Historical bundles have no evaluator identity protocol.
    identity = entry.get('evaluation')
    expected = 'handcrafted-v1' if options['Evaluator'] == 'Handcrafted' else None
    if options['Evaluator'] == 'Linear':
        expected = model_identity(Path(directory)/('model-'+str(options.get('ModelSHA256'))+'.txt'), options.get('ModelSHA256'))
    if identity is None or identity['evaluator'] != expected:
        raise ValueError('actual evaluator identity mismatch')
    if expected and expected.startswith('linear-'):
        model_hash = options.get('ModelSHA256')
        name = 'model-' + str(model_hash) + '.txt'
        if identity['model_sha256'] != model_hash or name not in artifacts:
            raise ValueError('model identity/artifact mismatch')
    elif identity['model_sha256'] is not None:
        raise ValueError('handcrafted evaluator cannot claim a model hash')


def model_identity(path, model_hash):
    from .model import load_model
    return 'linear-v2' if len(load_model(path,model_hash))==14 else 'linear-v1'


def validate_telemetry(record, directory):
    if not record['parameters'].get('pgn_telemetry'):
        return
    meta=record['tools'].get('telemetry',{})
    if meta.get('file')!='engine.log.gz' or 'engine.log.gz' not in record['artifacts']:
        raise ValueError('missing match telemetry')
    if 'raw_sha256' not in meta:
        return # New bundles use the compressed-file hash in artifacts.
    digest=hashlib.sha256();size=0
    with gzip.open(Path(directory)/'engine.log.gz','rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):
            digest.update(block);size+=len(block)
    if digest.hexdigest()!=meta.get('raw_sha256') or size!=meta.get('raw_bytes'):
        raise ValueError('match raw telemetry integrity mismatch')

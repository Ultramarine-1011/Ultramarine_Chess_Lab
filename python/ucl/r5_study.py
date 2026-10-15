"""Bounded R5 orchestration using existing match, benchmark and validation contracts."""
import argparse
import copy
import gzip
import json
from pathlib import Path
import shutil
import subprocess

from .records import git_state, sha256, utc_now, write_json

ROOT = Path(__file__).resolve().parents[2]
ORIGINAL = 'f933fe24ed983cb011b7a1bb0b9382c36a9b8d11'
MODEL = 'experiments/results/r4-models-v1/full.txt'
MODEL_SHA = '43e2e1ad509bfef9a529ce98706d6b64004d50166e115d7871a7666b05dd728e'
SEED = 20261016
EVIDENCE = ROOT/'docs/validation/r5'
CONFIGS = ROOT/'experiments/configs/r5'
RESULTS = ROOT/'experiments/results'
COMMON = {'Quiescence': True, 'UseTT': True, 'PVOrdering': True, 'Hash': 16, 'MoveOverhead': 10}


def engine(name, optimized=None, hand=False):
    revision = optimized or ORIGINAL
    return {'name': name, 'path': f'.tools/engines/{revision}/ucl.exe', 'revision': revision,
            'build': 'isolated CMake Release; MSVC /O2 /Ob2 /DNDEBUG; single search thread',
            'ucl_build_info': True,
            'options': {**COMMON, **({'Evaluator': 'Handcrafted'} if hand else
                {'ModelSHA256': MODEL_SHA, 'ModelFile': MODEL, 'Evaluator': 'Linear'})}}


def configs(optimized='HEAD'):
    original = engine('OriginalFull14')
    opt = engine('OptimizedFull14', optimized)
    if optimized == 'HEAD':
        opt['path'] = 'build/release/ucl.exe'
    hand = engine('Handcrafted', hand=True)
    for group, engines in {'A': [original, hand], 'B': [original, hand],
                           'C': [opt, hand], 'D': [opt, original]}.items():
        config = {'version': 1, 'comparison': 'ablation' if group in 'AB' else 'revision',
                  'seed': SEED, 'engines': engines, 'rounds': 200, 'games': 2, 'concurrency': 1,
                  'tc': '1000+10' if group == 'B' else '1+0.01', 'maxmoves': 150,
                  'timeout_seconds': 21600, 'pgn_telemetry': True,
                  'openings': {'path': 'experiments/results/r5-openings-v1/openings.epd',
                               'format': 'epd', 'order': 'sequential'}}
        if group == 'B':
            config['nodes'] = 50000
        yield group, config


def prepare():
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    CONFIGS.mkdir(parents=True, exist_ok=False)
    from .match import validate_config
    for group, config in configs():
        validate_config(config)
        write_json(CONFIGS/f'{group}.json', config)
    tracked = subprocess.check_output(['git', 'ls-files', 'experiments/results', 'docs/r3', 'docs/r4'],
                                      cwd=ROOT, text=True).splitlines()
    write_json(EVIDENCE/'r4-preservation-before.json', {n: sha256(ROOT/n) for n in tracked})
    src = ROOT/'.tools/engines'/ORIGINAL
    shutil.copyfile(src/'manifest.json', EVIDENCE/'original-build.json')
    shutil.copyfile(src/'build.log', EVIDENCE/'original-build.log')
    for name in ('fastchess-help.log', 'fastchess-version.log'):
        shutil.copyfile(ROOT/'.tools/r5-preflight'/name, EVIDENCE/name)
    write_json(EVIDENCE/'tool.json', {'path': '.tools/bin/fastchess.exe',
        'sha256': sha256(ROOT/'.tools/bin/fastchess.exe'),
        'r4_mac_revision': 'ebfd64cb7fac80d4822c50b07dca4fe934779d21',
        'r5_revision': 'f618e34540f94f4719ad3817950618dabe441318'})


def preflight():
    from .integrity import validate_bundle
    from .match import run_match
    schema = json.loads((ROOT/'schemas/experiment-v1.schema.json').read_text())
    outcomes = {}
    for group, config in configs():
        # Real runner/parser coverage of all four shapes before optimized code exists.
        # Explicit smoke identity; formal configuration keeps its strict comparison.
        config = copy.deepcopy(config)
        config.update(comparison='smoke', rounds=1, maxmoves=3, timeout_seconds=120)
        config['openings']['path'] = 'experiments/results/r4-openings-v1/openings.epd'
        for e in config['engines']:
            e['path'] = f'.tools/engines/{ORIGINAL}/ucl.exe'
            e['revision'] = ORIGINAL
        path = ROOT/'.tools/r5-preflight'/f'{group}.json'
        write_json(path, config)
        output = RESULTS/f'r5-preflight-v2-{group.lower()}'
        record = run_match(ROOT, path, output, '.tools/bin/fastchess.exe', allow_dirty=True)
        if record['status'] != 'completed':
            raise ValueError(f'preflight {group} failed: {record["error"]}')
        validate_bundle(output/'record.json', schema)
        outcomes[group] = {'record': str(output.relative_to(ROOT)/'record.json'),
                           'record_sha256': sha256(output/'record.json'), 'status': record['status']}
        if group == 'B':
            text = gzip.decompress((output/'engine.log.gz').read_bytes()).decode()
            go = [line for line in text.splitlines() if 'go ' in line and 'nodes' in line]
            stats = [json.loads(line.split('ucl_stats ', 1)[1]) for line in text.splitlines()
                     if 'info string ucl_stats ' in line]
            if not go or not stats or any(r['nodes'] != 50000 for r in stats):
                raise ValueError('nodes preflight did not exhaust exactly 50000 nodes')
            outcomes[group].update(go_commands=go, stats=stats)
    write_json(EVIDENCE/'preflight.json', {'code': git_state(ROOT), 'at': utc_now(), 'groups': outcomes})
    return outcomes


def freeze(optimized):
    from .match import capture_engine, validate_config, validate_comparison
    from .r5_openings import validate
    validate(RESULTS/'r5-openings-v1')
    controls = {}
    for group, config in configs(optimized):
        validate_config(config)
        entries = [capture_engine(ROOT, e, git_state(ROOT)['revision']) for e in config['engines']]
        validate_comparison(config, entries)
        write_json(CONFIGS/f'{group}.json', config)
        controls[group] = entries
    frozen = {'kind': 'r5-formal-freeze', 'at': utc_now(), 'code': git_state(ROOT),
              'original': ORIGINAL, 'optimized': optimized, 'engines': controls,
              'protocol_sha256': sha256(ROOT/'docs/r5/protocol.md'),
              'analysis_sha256': sha256(Path(__file__)), 'tool_sha256': sha256(ROOT/'.tools/bin/fastchess.exe'),
              'openings_sha256': sha256(RESULTS/'r5-openings-v1/openings.epd'),
              'configs': {g: sha256(CONFIGS/f'{g}.json') for g in 'ABCD'}}
    target = EVIDENCE/'formal-freeze.json'
    if target.exists():
        raise ValueError('formal freeze already exists')
    write_json(target, frozen)
    return frozen


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('operation', choices=['prepare', 'preflight', 'freeze'])
    p.add_argument('--optimized')
    a = p.parse_args()
    result = {'prepare': prepare, 'preflight': preflight, 'freeze': lambda: freeze(a.optimized)}[a.operation]()
    print(json.dumps(result, indent=2))

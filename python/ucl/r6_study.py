"""R6 frozen configurations, actual sequential matches and reused telemetry analysis."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

from .match import run_match
from .r5_analysis import analyze_group
from .r5_study import COMMON
from .r6_data import ROOT, SEED
from .records import git_state, sha256, write_json


def configure(study, engine, output):
    study, output = Path(study), Path(output)
    if (study/'freeze.json').exists():
        raise FileExistsError('models and schedule already frozen')
    s = json.loads((study/'selection.json').read_text(encoding='utf-8'))
    revision = json.loads(subprocess.check_output([str(Path(engine).resolve()), '--build-info'], text=True))['revision']
    def entry(name):
        options = {**COMMON, 'Evaluator': 'Handcrafted' if name == 'Handcrafted' else 'Linear'}
        if name != 'Handcrafted':
            path = study/s['models'][name]['model_file']
            options.update(ModelFile=path.as_posix(), ModelSHA256=sha256(path))
        return {'name': name, 'path': Path(engine).as_posix(), 'revision': revision,
                'build': 'Windows CMake Release MSVC /O2 /Ob2 /DNDEBUG, one search thread',
                'ucl_build_info': True, 'options': options}
    configs = {}
    candidate = s['candidate']
    for group, names in {'A': ('G', 'Handcrafted'), 'B': (candidate, 'Handcrafted'),
                         'C': (candidate, 'G'), 'D': (candidate, 'G')}.items():
        c = {'version': 1, 'comparison': 'ablation', 'seed': SEED, 'engines': [entry(n) for n in names],
             'rounds': 200, 'games': 2, 'concurrency': 1, 'tc': '1+0.01' if group != 'D' else '1000+10',
             'maxmoves': 150, 'timeout_seconds': 21600, 'pgn_telemetry': True,
             'openings': {'path': 'experiments/results/r6-data-v1/openings.epd', 'format': 'epd', 'order': 'sequential'}}
        if group == 'D':
            c['nodes'] = 50000
        write_json(output/f'{group}.json', c)
        configs[group] = sha256(output/f'{group}.json')
    engines = [entry(n) for n in dict.fromkeys(('Handcrafted', 'G', 'T', s['mixed_model'], candidate))]
    write_json(output/'benchmark.json', {'version': 1, 'seed': SEED, 'suite': 'experiments/positions/r2-v1.json',
                                        'repeats': 3, 'limits': [{'depth': 4}, {'nodes': 50000}], 'engines': engines})
    for e in engines:
        if e['name'] != 'Handcrafted':
            write_json(output/f'static-{e["name"]}.json', {'version': 1, 'seed': SEED, 'suite': 'experiments/positions/r2-v1.json',
                       'repeats': 1, 'limits': [{'depth': 1}], 'static_evaluation': True, 'engines': [entry('Handcrafted'), e]})
    freeze = {'selection_sha256': sha256(study/'selection.json'), 'candidate': candidate,
              'models': {n: m['model_sha256'] for n, m in s['models'].items() if 'model_sha256' in m},
              'engine_sha256': sha256(engine), 'engine_revision': revision,
              'openings_sha256': sha256(ROOT/'experiments/results/r6-data-v1/openings.epd'),
              'configs': configs, 'code': git_state(ROOT), 'confirmatory': 'C only',
              'fastchess_sha256': sha256(ROOT/'.tools/bin/fastchess.exe')}
    write_json(study/'freeze.json', freeze)
    return freeze


def run(configs, output, fastchess):
    output = Path(output)
    freeze = json.loads((ROOT/'experiments/results/r6-models-v1/freeze.json').read_text(encoding='utf-8'))
    for g, h in freeze['configs'].items():
        if sha256(Path(configs)/f'{g}.json') != h:
            raise ValueError('match configuration changed after freeze')
    if sha256(ROOT/fastchess) != freeze['fastchess_sha256']:
        raise ValueError('match tool changed after freeze')
    if sha256(ROOT/'experiments/results/r6-data-v1/openings.epd') != freeze['openings_sha256']:
        raise ValueError('match openings changed after freeze')
    first = json.loads((Path(configs)/'A.json').read_text(encoding='utf-8'))
    if any(sha256(ROOT/e['path']) != freeze['engine_sha256'] for e in first['engines']):
        raise ValueError('match binary changed after freeze')
    for group in 'ABCD':
        target = output/group
        if target.exists():
            record = json.loads((target/'record.json').read_text(encoding='utf-8'))
            if record['status'] == 'completed':
                print(f'{group}: already complete, preserved', flush=True)
                continue
            raise ValueError('existing incomplete match requires explicit missing-game recovery')
        print(f'{group}: starting frozen 400 games', flush=True)
        def capture(when):
            if sys.platform == 'win32':
                dest = ROOT/f'docs/validation/r6/host-{group}-{when}.json'
                dest.parent.mkdir(parents=True, exist_ok=True)
                subprocess.run(['powershell', '-NoProfile', '-File', str(ROOT/'docs/validation/r5/capture-host.ps1'),
                                '-Output', str(dest)], check=True, capture_output=True)
        capture('before')
        record = run_match(ROOT, Path(configs)/f'{group}.json', target, fastchess, formal=True)
        capture('after')
        if record['status'] != 'completed':
            raise RuntimeError(f'{group}: {record["error"]}')
        print(f'{group}: completed', flush=True)


def analyze(input_path, output):
    result = {'kind': 'r6-playing-strength', 'groups': {}, 'confirmatory_family': ['C'], 'code': git_state(ROOT)}
    for group in 'ABCD':
        r = analyze_group(group, Path(input_path)/group, Path(output)/group, node_group='D')
        ci = r['bootstrap']['ci95']
        r.pop('elo_ci98_75')
        r['bootstrap'].pop('ci98_75_bonferroni_four')
        r['confirmatory_vs_half'] = ('above' if ci[0] > .5 else 'below' if ci[1] < .5 else 'inconclusive') if group == 'C' else 'exploratory'
        write_json(Path(output)/group/'analysis.json', r)
        result['groups'][group] = r
    write_json(Path(output)/'summary.json', result)
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('operation', choices=['configure', 'matches', 'analyze'])
    p.add_argument('--study', default='experiments/results/r6-models-v1')
    p.add_argument('--engine', default='build/release/ucl.exe')
    p.add_argument('--input', default='experiments/configs/r6')
    p.add_argument('--output', required=True)
    p.add_argument('--fastchess', default='.tools/bin/fastchess.exe')
    a = p.parse_args()
    if a.operation == 'configure':
        print(configure(a.study, a.engine, a.output))
    elif a.operation == 'matches':
        run(a.input, a.output, a.fastchess)
    else:
        print(json.dumps({g: r['statistics'] for g, r in analyze(a.input, a.output)['groups'].items()}, indent=2))

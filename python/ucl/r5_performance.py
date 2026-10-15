"""Alternating Windows measurements, preserving existing benchmark-v1 bundles."""
import argparse
import json
from pathlib import Path
import shutil
import statistics
import subprocess

from .benchmark import run_benchmark
from .integrity import validate_bundle
from .r5_study import ROOT, RESULTS, CONFIGS, EVIDENCE, SEED, engine
from .records import git_state, sha256, utc_now, write_json


def host(path):
    subprocess.run(['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
        str(EVIDENCE/'capture-host.ps1'), '-Output', str(Path(path).resolve())],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=True)


def prepare(optimized):
    base = {'version': 1, 'seed': SEED, 'suite': 'experiments/positions/r2-v1.json'}
    write_json(CONFIGS/'benchmark-search.json', {**base, 'repeats': 5,
        'limits': [{'depth': 3}, {'depth': 4}, {'nodes': 50000}],
        'engines': [engine('Handcrafted', hand=True), engine('OriginalFull14'), engine('OptimizedFull14', optimized)]})
    for block, order in enumerate(('OP', 'PO', 'OP')):
        for kind in order:
            name = 'OriginalFull14' if kind == 'O' else 'OptimizedFull14'
            write_json(CONFIGS/f'benchmark-static-{block}-{kind}.json', {**base, 'repeats': 1,
                'limits': [{'depth': 3}], 'static_evaluation': True,
                'engines': [engine(name, optimized if kind=='P' else None), engine('Handcrafted', hand=True)]})


def summarize(directory):
    directory = Path(directory)
    schema = json.loads((ROOT/'schemas/benchmark-v1.schema.json').read_text())
    main = validate_bundle(directory/'search/record.json', schema)
    statics, blocks = {}, []
    for block, order in enumerate(('OP', 'PO', 'OP')):
        entry = {'block': block, 'order': order}
        for kind in order:
            r = validate_bundle(directory/f'static-{block}-{kind}/record.json', schema)
            s = r['tools']['static_evaluation']['summary']
            statics.setdefault(kind, []).append(s)
            entry[kind] = s
        entry['original_over_optimized_ratio'] = entry['O']['mean_position_median_linear_ns']/entry['P']['mean_position_median_linear_ns']
        blocks.append(entry)
    summary = []
    for row in main['summary']:
        data = [r for r in main['rows'] if r['engine']==row['engine'] and r['limit']==row['limit']]
        medians = {key: sum(statistics.median(r[key] for r in data if r['position']==p)
                   for p in sorted({r['position'] for r in data}))
                   for key in ('qnodes', 'tt_probes', 'tt_hits', 'tt_cutoffs', 'tt_stores', 'elapsed_us')}
        summary.append({**row, 'per_position_median_sums': medians,
                        'completed_depths': sorted(r['depth'] for r in data)})
    controls = {}
    for row in main['rows']:
        if row['engine']=='Handcrafted': continue
        key = (row['position'], json.dumps(row['limit'], sort_keys=True), row['repeat'])
        values = {k: row[k] for k in ('depth','score_cp','pv','move','nodes','qnodes',
                                      'tt_probes','tt_hits','tt_cutoffs','tt_stores','pv_order_hits','tt_order_hits')}
        if key in controls and controls[key]!=values:
            raise ValueError('Full14 semantic mismatch in performance study')
        controls[key] = values
    return {'static_blocks': blocks, 'static': {kind: {
        'mean_of_block_position_medians_ns': statistics.mean(s['mean_position_median_linear_ns'] for s in rows),
        'handcrafted_mean_ns': statistics.mean(s['mean_position_median_handcrafted_ns'] for s in rows)}
        for kind, rows in statics.items()}, 'search': summary,
        'full14_search_semantics_equal': True, 'search_queries': len(main['rows'])}


def run():
    if git_state(ROOT)['dirty']: raise ValueError('commit before formal performance measurements')
    output = RESULTS/'r5-performance-v1'; output.mkdir(parents=True, exist_ok=False)
    index = {'kind': 'r5-performance', 'code': git_state(ROOT), 'started_at': utc_now(), 'status': 'running', 'error': None}
    write_json(output/'index.json', index)
    try:
        if shutil.disk_usage(ROOT).free < 10*1024**3: raise ValueError('disk guard failed')
        host(output/'host-before.json')
        for block, order in enumerate(('OP', 'PO', 'OP')):
            for kind in order:
                record = run_benchmark(ROOT, CONFIGS/f'benchmark-static-{block}-{kind}.json', output/f'static-{block}-{kind}')
                if record['status']!='completed': raise ValueError(record['error'])
            host(output/f'host-block-{block}.json')
        record = run_benchmark(ROOT, CONFIGS/'benchmark-search.json', output/'search')
        if record['status']!='completed': raise ValueError(record['error'])
        host(output/'host-after.json')
        index.update(status='PASS', summary=summarize(output))
    except Exception as exc:
        index.update(status='FAIL', error=f'{type(exc).__name__}: {exc}')
    finally:
        index['finished_at'] = utc_now()
        index['files'] = {str(p.relative_to(output)): {'sha256': sha256(p), 'bytes': p.stat().st_size}
                          for p in output.rglob('*') if p.is_file() and p!=output/'index.json'}
        write_json(output/'index.json', index)
    return index


if __name__=='__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('operation', choices=['prepare','run','validate']); p.add_argument('--optimized')
    a = p.parse_args()
    r = prepare(a.optimized) if a.operation=='prepare' else run() if a.operation=='run' else summarize(RESULTS/'r5-performance-v1')
    print(json.dumps(r, indent=2))
    if isinstance(r, dict) and r.get('status')=='FAIL': raise SystemExit(1)

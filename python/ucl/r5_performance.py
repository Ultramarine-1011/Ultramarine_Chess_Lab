"""Alternating Windows measurements, preserving existing benchmark-v1 bundles."""
import argparse
import json
from pathlib import Path
import statistics

from .benchmark import run_benchmark
from .integrity import validate_bundle
from .r5_study import ROOT, CONFIGS
from .records import write_json


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


def run(output):
    output = Path(output)
    for block, order in enumerate(('OP', 'PO', 'OP')):
        for kind in order:
            record = run_benchmark(ROOT, CONFIGS/f'benchmark-static-{block}-{kind}.json',
                                   output/f'static-{block}-{kind}', formal=True)
            if record['status'] != 'completed':
                raise RuntimeError(record['error'])
    record = run_benchmark(ROOT, CONFIGS/'benchmark-search.json', output/'search', formal=True)
    if record['status'] != 'completed':
        raise RuntimeError(record['error'])
    result = summarize(output)
    write_json(output/'summary.json', result)
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('operation', choices=['run', 'validate'])
    p.add_argument('--output', required=True)
    a = p.parse_args()
    print(json.dumps(run(a.output) if a.operation == 'run' else summarize(a.output), indent=2))

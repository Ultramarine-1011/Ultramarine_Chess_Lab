"""Bounded R5 orchestration using existing match, benchmark and validation contracts."""
import argparse
import json
from pathlib import Path

from .records import write_json

ROOT = Path(__file__).resolve().parents[2]
ORIGINAL = 'f933fe24ed983cb011b7a1bb0b9382c36a9b8d11'
MODEL = 'experiments/results/r4-models-v1/full.txt'
MODEL_SHA = '43e2e1ad509bfef9a529ce98706d6b64004d50166e115d7871a7666b05dd728e'
SEED = 20261016
EVIDENCE = ROOT/'docs/validation/r5'
CONFIGS = ROOT/'experiments/configs/r5'
RESULTS = ROOT/'experiments/results'
COMMON = {'Quiescence': True, 'UseTT': True, 'PVOrdering': True, 'Hash': 16, 'MoveOverhead': 10}


def matches(output, fastchess):
    """Execute the stored schedule only when explicitly invoked."""
    from .match import run_match
    records = {}
    for group in 'ABCD':
        record = run_match(ROOT, CONFIGS/f'{group}.json', Path(output)/group, fastchess, formal=True)
        if record['status'] != 'completed':
            raise RuntimeError(f"{group}: {record['error']}")
        records[group] = record['results']
    write_json(Path(output)/'summary.json', records)
    return records


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', required=True)
    p.add_argument('--fastchess', default='fastchess')
    a = p.parse_args()
    print(json.dumps(matches(a.output, a.fastchess), indent=2))

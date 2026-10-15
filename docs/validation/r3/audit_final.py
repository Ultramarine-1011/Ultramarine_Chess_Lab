"""Reproduce the final R3 audit using existing UCL validators and PGN builder."""
from collections import Counter
import json
import os
from pathlib import Path
import subprocess
import sys

import chess.pgn

from ucl.dataset import validate_dataset
from ucl.records import write_json
from ucl.report import CheckedGameBuilder, check_game_result
from ucl.training import TrainingSpec, read_features, validate_model_manifest

ROOT = Path(__file__).resolve().parents[3]
os.chdir(ROOT)
checks = {f'dataset_v{n}': validate_dataset(f'experiments/results/r3-data-v{n}')['counts'] for n in (1, 2)}
spec = TrainingSpec('experiments/results/r3-data-v2/manifest.json', 'handcrafted-v1', 20261015,
                    'white-game-result', 'experiments/results/r3-data-v2/splits.json')
rows, _ = read_features('experiments/results/r3-features-v2/manifest.json', spec)
checks['feature_rows'] = len(rows)
checks['model_sha256'] = validate_model_manifest('experiments/results/r3-model-v1/model-manifest.json')['model_sha256']
openings, natural = Counter(), Counter()
with Path('experiments/results/r3-match-final-20261015/games.pgn').open() as stream:
    while (game := chess.pgn.read_game(stream, Visitor=CheckedGameBuilder)) is not None:
        final = check_game_result(game, True)
        openings[game.board().epd()] += 1
        natural[str(final.outcome(claim_draw=True).termination)] += 1
expected = Path('experiments/openings/r3-v1.epd').read_text().splitlines()
assert set(openings) == set(expected) and len(openings) == 16 and set(openings.values()) == {2}
checks['opening_coverage'] = {'unique': len(openings), 'games_each': 2, 'natural': dict(natural)}
tracked = subprocess.check_output(['git', 'ls-files', 'experiments/results/*/record.json'], text=True).splitlines()
records = sorted(set(tracked + ['experiments/results/r3-benchmark-final-20261015/record.json',
                                'experiments/results/r3-match-final-20261015/record.json']))
for operation, key in [('validate', 'bundle_validation'), ('report', 'reports')]:
    checks[key] = []
    for record in records:
        args = [sys.executable, '-m', 'ucl.cli', operation, record]
        result = subprocess.run(args, text=True, capture_output=True)
        item = {'command': args, 'exit_code': result.returncode}
        if operation == 'validate':
            item['output'] = result.stdout + result.stderr
        checks[key].append(item)
        assert result.returncode == 0, (args, result.stdout, result.stderr)
checks['search_and_handcrafted_source_unchanged'] = not subprocess.check_output([
    'git', 'diff', 'b9fac65cbcb68b492090b076f333dff861580a86', 'HEAD', '--',
    'engine/src/search.cpp', 'engine/src/evaluator.cpp'])
assert checks['search_and_handcrafted_source_unchanged']
write_json(ROOT/'docs/validation/r3/r35-final-audit.json', checks)
print(f"Validated both datasets, features/model, 16 openings and {len(records)} retained bundles/reports")

"""Fixed-capacity R6 target comparison; validation selection then one held-out test."""
import argparse
from collections import defaultdict
import json
import math
from pathlib import Path
import subprocess

import numpy as np
from scipy.special import expit

from .feature_data import WEIGHTS
from .model import encode_model, load_model
from .r4_analysis import game_means
from .r4_training import arrays, optimize, loss_values
from .r6_data import ROOT, SEED, read_rows, ranking_rows
from .records import git_state, sha256, write_json

LAMBDAS = [.0001, .001, .01, .1, 1.]


def verify_ranking(rows, children, which):
    expected = ranking_rows(rows, which)
    if len(expected) != len(children):
        raise ValueError('incomplete legal candidate set')
    for e, actual in zip(expected, children, strict=True):
        if any(actual.get(k) != v for k, v in e.items()):
            raise ValueError('ranking root/child/split mismatch')


def losses(rows, weights):
    x = np.asarray([r['features'] for r in rows], dtype=float)
    y = np.asarray([r['game_result'] for r in rows])
    t = np.asarray([r['teacher_evaluation']['target'] for r in rows])
    result = {'game_'+k: v for k, v in loss_values(x, y, weights).items()}
    result.update({'teacher_'+k: v for k, v in loss_values(x, t, weights).items()})
    cp = np.asarray([r['teacher_evaluation']['white_cp']
                     if r['teacher_evaluation']['kind'] == 'cp' else np.nan for r in rows])
    result['cp_mae'] = np.abs(np.clip(x@weights, -2000, 2000)-np.clip(cp, -2000, 2000))
    result['cp_mse'] = result['cp_mae']**2
    return result


def equal_game_finite(values, rows):
    mask = np.isfinite(values)
    selected = [r for r, keep in zip(rows, mask, strict=True) if keep]
    return float(game_means(values[mask], selected).mean()) if selected else None


def metrics(rows, weights):
    result = {'positions': len(rows), 'games': len({r['game_id'] for r in rows})}
    result.update({k: equal_game_finite(v, rows) for k, v in losses(rows, weights).items()})
    result['cp_rmse'] = result['cp_mse']**.5 if result['cp_mse'] is not None else None
    p = expit(np.asarray([r['features'] for r in rows])@weights/400)
    bins = []
    for i in range(10):
        ix = [j for j, value in enumerate(p) if i/10 <= value < (i+1)/10 or i == 9 and value == 1]
        if ix:
            bins.append({'range': [i/10, (i+1)/10], 'positions': len(ix),
                         'mean_prediction': float(p[ix].mean()),
                         'mean_teacher': float(np.mean([rows[j]['teacher_evaluation']['target'] for j in ix])),
                         'mean_result': float(np.mean([rows[j]['game_result'] for j in ix]))})
    result['calibration_position_weighted'] = bins
    return result


def rank_values(children, weights):
    grouped = defaultdict(list)
    for r in children:
        grouped[r['root_id']].append(r)
    output = []
    for root, group in sorted(grouped.items()):
        sign = 1 if group[0]['root_turn'] else -1
        teacher = np.asarray([r['teacher_evaluation']['white_order']*sign for r in group])
        static = np.asarray([np.dot(r['features'], weights)*sign for r in group])
        # Search handles terminal positions before static evaluation as does deployment.
        for i, r in enumerate(group):
            if r['teacher_evaluation']['kind'] == 'terminal':
                static[i] = teacher[i]
        clear, all_pairs = [], []
        for i in range(len(group)):
            for j in range(i):
                gap = teacher[i]-teacher[j]
                if gap == 0:
                    continue
                delta = (static[i]-static[j])*np.sign(gap)
                accuracy = 1. if delta > 0 else .5 if delta == 0 else 0.
                all_pairs.append(accuracy)
                if abs(gap) >= 100:
                    clear.append(accuracy)
        top = int(np.argmax(static)) # group order is lexicographic UCI, fixed tie rule.
        output.append({'root_id': root, 'game_id': group[0]['game_id'], 'candidates': len(group),
                       'clear_pairs': len(clear), 'all_pairs': len(all_pairs),
                       'accuracy': float(np.mean(clear)) if clear else None,
                       'all_accuracy': float(np.mean(all_pairs)) if all_pairs else None,
                       'teacher_regret_order_units': int(teacher.max()-teacher[top]),
                       'selected_move': group[top]['move']})
    return output


def rank_metrics(values):
    eligible = [r for r in values if r['accuracy'] is not None]
    return {'positions': len(values), 'eligible_positions': len(eligible),
            'clear_pairs': sum(r['clear_pairs'] for r in values),
            'primary_accuracy': float(game_means([r['accuracy'] for r in eligible], eligible).mean()) if eligible else None,
            'all_accuracy': equal_game_finite(np.asarray([r['all_accuracy'] if r['all_accuracy'] is not None else np.nan
                                                        for r in values]), values),
            'mean_teacher_regret_order_units': float(np.mean([r['teacher_regret_order_units'] for r in values])),
            'zero_regret_fraction': float(np.mean([r['teacher_regret_order_units'] == 0 for r in values]))}


def strata(rows):
    def phase(r):
        import chess
        b = chess.Board(r['fen'])
        return min(24, sum(len(b.pieces(pt, c))*v for c in chess.COLORS for pt, v in
                          ((chess.KNIGHT, 1), (chess.BISHOP, 1), (chess.ROOK, 2), (chess.QUEEN, 4))))
    return {'white_to_move': [r for r in rows if r['fen'].split()[1] == 'w'],
            'black_to_move': [r for r in rows if r['fen'].split()[1] == 'b'],
            'draw': [r for r in rows if r['game_result'] == .5],
            'early_ply16_40': [r for r in rows if r['ply'] <= 40],
            'opening_phase17_24': [r for r in rows if phase(r) >= 17],
            'middle_phase9_16': [r for r in rows if 9 <= phase(r) <= 16],
            'endgame_phase0_8': [r for r in rows if phase(r) <= 8]}


def fit(input_path, rank_path, dataset, output):
    output = Path(output)
    if (output/'freeze.json').exists() or (output/'test-results.json').exists():
        raise ValueError('study already frozen')
    rows = read_rows(input_path)
    train = [r for r in rows if r['split'] == 'train']
    val = [r for r in rows if r['split'] == 'validation']
    children = read_rows(rank_path)
    verify_ranking(rows, children, 'validation')
    output.mkdir(parents=True, exist_ok=True)
    _, x, y, q = arrays(train, 'train')
    _, vx, vy, vq = arrays(val, 'validation')
    t = np.asarray([r['teacher_evaluation']['target'] for r in train])
    vt = np.asarray([r['teacher_evaluation']['target'] for r in val])
    models, fits = {}, {}
    for name, alpha in [('G', 0.), ('T', 1.), ('M05', .5), ('M08', .8)]:
        target, vtarget = alpha*t+(1-alpha)*y, alpha*vt+(1-alpha)*vy
        candidates = []
        for penalty in LAMBDAS:
            c = optimize(x, target, q, list(range(14)), penalty)
            c['validation_target_bce'] = float(vq@loss_values(vx, vtarget, c['weights'])['bce'])
            candidates.append(c)
        fits[name] = candidates
        if not all(c['success'] for c in candidates):
            write_json(output/'fits.json', fits)
            raise ValueError('optimizer did not converge')
        models[name] = {**min(candidates, key=lambda c: (c['validation_target_bce'], -c['lambda'])), 'alpha': alpha}
    models['Handcrafted'] = {'weights': WEIGHTS+[0.]*6}
    old = ROOT/'experiments/results/r4-models-v1/full.txt'
    models['R4Full14'] = {'weights': load_model(old, sha256(old)), 'historical_sha256': sha256(old)}
    for name, m in models.items():
        m['validation'] = metrics(val, m['weights'])
        m['ranking'] = rank_metrics(rank_values(children, m['weights']))
        m['validation_strata'] = {s: metrics(rs, m['weights']) for s, rs in strata(val).items() if rs}
        if name in ('Handcrafted', 'R4Full14'):
            continue
        text = encode_model(m['weights'], sha256(Path(dataset)/'manifest.json'), sha256(Path(dataset)/'splits.json'))
        (output/f'{name}.txt').write_bytes(text.encode('ascii'))
        m.update(model_file=f'{name}.txt', model_sha256=sha256(output/f'{name}.txt'))
    key = lambda n: (-models[n]['ranking']['primary_accuracy'], models[n]['validation']['teacher_bce'], n)
    candidate = min(('T', 'M05', 'M08'), key=key)
    best_m = min(('M05', 'M08'), key=key)
    result = {'kind': 'r6-validation-selection', 'candidate': candidate, 'mixed_model': best_m,
              'models': models, 'input': str(input_path), 'input_sha256': sha256(input_path),
              'validation_rank_sha256': sha256(rank_path), 'code': git_state(ROOT),
              'configuration': {'lambdas': LAMBDAS, 'teacher_scale': 400, 'clip': 2000,
                                'rms': 'train-only equal-game', 'intercept': 0, 'capacity': 14},
              'test_evaluated': False}
    write_json(output/'fits.json', fits)
    write_json(output/'selection.json', result)
    return result


def interval(values, rows):
    v = np.asarray(values, dtype=float)
    mask = np.isfinite(v)
    rs = [r for r, keep in zip(rows, mask, strict=True) if keep]
    means = game_means(v[mask], rs)
    if len(means) == 0:
        return {'difference': None, 'ci95': None, 'games': 0}
    rng = np.random.default_rng(SEED)
    draws = rng.integers(0, len(means), size=(2000, len(means)))
    return {'difference': float(means.mean()), 'ci95': np.quantile(means[draws].mean(axis=1), [.025, .975]).tolist(),
            'games': len(means), 'resamples': 2000}


def test(study, rank_path):
    study = Path(study)
    if (study/'test-results.json').exists():
        raise FileExistsError('independent test already evaluated')
    freeze = json.loads((study/'freeze.json').read_text(encoding='utf-8'))
    if sha256(study/'selection.json') != freeze['selection_sha256']:
        raise ValueError('selection changed')
    s = json.loads((study/'selection.json').read_text(encoding='utf-8'))
    if sha256(s['input']) != s['input_sha256']:
        raise ValueError('dataset changed')
    for n, h in freeze['models'].items():
        if sha256(study/f'{n}.txt') != h:
            raise ValueError('frozen model changed')
    rows = [r for r in read_rows(s['input']) if r['split'] == 'test']
    children = read_rows(rank_path)
    verify_ranking(rows, children, 'test')
    names = list(dict.fromkeys(('G', 'T', s['mixed_model'], s['candidate'], 'Handcrafted', 'R4Full14')))
    weights = {n: s['models'][n]['weights'] for n in names}
    rank = {n: rank_values(children, w) for n, w in weights.items()}
    a, b = s['candidate'], 'G'
    la, lb = losses(rows, weights[a]), losses(rows, weights[b])
    contrasts = {k: interval(la[k]-lb[k], rows) for k in ('game_bce', 'teacher_bce', 'cp_mae')}
    contrasts['ranking_accuracy'] = interval([ra['accuracy']-rb['accuracy'] if ra['accuracy'] is not None else np.nan
                                             for ra, rb in zip(rank[a], rank[b], strict=True)], rank[a])
    result = {'kind': 'r6-independent-test', 'code': git_state(ROOT), 'candidate': a,
              'freeze_sha256': sha256(study/'freeze.json'), 'rank_sha256': sha256(rank_path),
              'models': {n: metrics(rows, w) for n, w in weights.items()},
              'ranking': {n: rank_metrics(v) for n, v in rank.items()},
              'strata': {s: {n: metrics(rs, w) for n, w in weights.items()} for s, rs in strata(rows).items() if rs},
              'candidate_minus_G': contrasts, 'interval_scope': 'descriptive whole-game clusters, not familywise claims'}
    write_json(study/'test-ranking-details.json', rank)
    write_json(study/'test-results.json', result)
    return result


def verify(study, engine):
    study = Path(study)
    s = json.loads((study/'selection.json').read_text(encoding='utf-8'))
    rows = read_rows(s['input'])
    if len({r['position_id'] for r in rows}) != len(rows):
        raise ValueError('duplicate or mirrored dataset position')
    memberships = defaultdict(set)
    for r in rows:
        memberships[r['game_id']].add(r['split'])
        e = r['teacher_evaluation']
        if r['label'] != r['game_result'] or not 0 <= e['target'] <= 1:
            raise ValueError('bad result/teacher label')
        if e['kind'] == 'cp' and e['white_cp'] != e['stm_cp']*(1 if r['fen'].split()[1] == 'w' else -1):
            raise ValueError('teacher perspective mismatch')
    if any(len(v) != 1 for v in memberships.values()):
        raise ValueError('whole-game split leak')
    checked = {}
    for n, m in s['models'].items():
        if 'model_file' not in m:
            continue
        p = study/m['model_file']
        if load_model(p, m['model_sha256']) != m['weights']:
            raise ValueError('model deployment weights changed')
        proc = subprocess.run([str(Path(engine).resolve()), '--infer', str(p.resolve()), m['model_sha256']],
                              input='\n'.join(r['fen'] for r in rows)+'\n', text=True, capture_output=True, check=True)
        actual = [json.loads(line) for line in proc.stdout.splitlines()]
        max_error = 0.
        for r, out in zip(rows, actual, strict=True):
            expected = sum(a*b for a, b in zip(r['features'], m['weights'], strict=True))
            rounded = math.floor(expected+.5) if expected >= 0 else math.ceil(expected-.5)
            if out['score_cp'] != rounded*(1 if r['fen'].split()[1] == 'w' else -1):
                raise ValueError('C++ rounded perspective mismatch')
            max_error = max(max_error, abs(out['white_score']-expected))
        if max_error > 1e-9:
            raise ValueError('C++ raw inference mismatch')
        checked[n] = {'positions': len(rows), 'max_white_error': max_error, 'rounded_cp_exact': True}
    e = [r['teacher_evaluation'] for r in rows]
    result = {'status': 'PASS', 'positions': len(rows), 'games': len(memberships), 'models': checked,
              'teacher_kinds': {k: sum(t['kind'] == k for t in e) for k in ('cp', 'mate', 'terminal')},
              'depth_quantiles': np.quantile([t['depth'] for t in e], [0, .5, 1]).tolist(),
              'actual_final_nodes_sum': sum(t['final_nodes'] for t in e),
              'requested_nodes_per_position': 20000, 'perspective': 'white; every cp checked against STM',
              'scope': 'deployment/data correctness; no test performance metrics evaluated'}
    write_json(study/'verification.json', result)
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('operation', choices=['fit', 'test', 'verify'])
    p.add_argument('--input')
    p.add_argument('--rank')
    p.add_argument('--engine', default='build/release/ucl.exe')
    p.add_argument('--dataset', default='experiments/results/r6-data-v1')
    p.add_argument('--output', required=True)
    a = p.parse_args()
    if a.operation == 'verify':
        print(verify(a.output, a.engine))
    else:
        r = fit(a.input, a.rank, a.dataset, a.output) if a.operation == 'fit' else test(a.output, a.rank)
        print(json.dumps({k: r[k] for k in ('kind', 'candidate')}, indent=2))

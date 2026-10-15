"""Reproducible fractional logistic linear evaluation using the existing Trainer boundary."""
from dataclasses import asdict, dataclass
import gzip
import importlib.metadata
import json
from pathlib import Path
import platform
import time
from typing import Protocol

import numpy as np
from scipy.optimize import minimize
from scipy.special import expit

from .dataset import SEED
from .feature_data import VERSION, WEIGHTS, validate_vector
from .model import encode_model, load_model
from .records import git_state, hardware, sha256, validate_record, write_json


@dataclass(frozen=True)
class TrainingSpec:
    dataset_manifest: str
    features: str
    seed: int
    target: str
    split_manifest: str


class Trainer(Protocol):
    def fit(self, spec: TrainingSpec, output_directory: str) -> str:
        """Return path to a model manifest with weights, feature version and metrics."""
        ...


ROOT = Path(__file__).resolve().parents[2]
LAMBDAS = (0., .0001, .001, .01, .1, 1.)
TAU = 400.


def check_arrays(x, y):
    x, y = np.asarray(x, dtype=np.float64), np.asarray(y, dtype=np.float64)
    if x.ndim != 2 or x.shape[1] != 8 or y.shape != (len(x),) or not len(x):
        raise ValueError('invalid training dimensions')
    if not np.isfinite(x).all() or not np.isfinite(y).all() or not np.isin(y, [0, .5, 1]).all():
        raise ValueError('invalid training values/labels')
    return x, y


def objective(beta, x, y, prior, penalty):
    z = x @ beta
    delta = beta - prior
    loss = np.mean(np.logaddexp(0., z) - y*z) + penalty/2 * (delta @ delta)
    grad = x.T @ (expit(z)-y) / len(y) + penalty * delta
    return float(loss), grad


def optimize(x, y, penalty):
    x, y = check_arrays(x, y)
    if not np.isfinite(penalty) or penalty < 0:
        raise ValueError('invalid regularization')
    rms = np.sqrt(np.mean(x*x, axis=0))
    rms[rms == 0] = 1.
    prior = np.asarray(WEIGHTS, dtype=float)*rms/TAU
    start = time.perf_counter()
    fit = minimize(objective, prior, args=(x/rms, y, prior, penalty), jac=True,
                   method='L-BFGS-B', options={'maxiter': 1000, 'gtol': 1e-9, 'ftol': 1e-12})
    result = {'weights': (fit.x*TAU/rms).tolist(), 'rms': rms.tolist(),
              'success': bool(fit.success), 'message': str(fit.message), 'iterations': int(fit.nit),
              'objective': float(fit.fun), 'gradient_inf': float(np.max(np.abs(fit.jac))),
              'seconds': time.perf_counter()-start, 'lambda': penalty}
    return result


def metrics(x, y, weights):
    x, y = check_arrays(x, y)
    z = x @ np.asarray(weights) / TAU
    return {'positions': len(y), 'bce': float(np.mean(np.logaddexp(0., z)-y*z)),
            'brier': float(np.mean((expit(z)-y)**2))}


def read_features(manifest_path, spec):
    p = Path(manifest_path)
    m = json.loads(p.read_text())
    if spec.features != VERSION or m['feature_version'] != VERSION or spec.target != 'white-game-result':
        raise ValueError('training feature/target version mismatch')
    for actual, expected in ((sha256(spec.dataset_manifest), m['dataset_manifest_sha256']),
                             (sha256(spec.split_manifest), m['splits_sha256']),
                             (sha256(p.parent/'features.jsonl.gz'), m['features_sha256'])):
        if actual != expected:
            raise ValueError('training input hash mismatch')
    rows = [json.loads(line) for line in gzip.decompress((p.parent/'features.jsonl.gz').read_bytes()).decode().splitlines()]
    games = json.loads(Path(spec.split_manifest).read_text())
    if json.loads(Path(spec.dataset_manifest).read_text())['seed'] != spec.seed:
        raise ValueError('dataset/training seed mismatch')
    if len(rows) != m['count'] or len({r['position_id'] for r in rows}) != len(rows):
        raise ValueError('feature count/position duplication mismatch')
    for r in rows:
        validate_vector({k:r[k] for k in ('feature_version', 'features', 'handcrafted_cp')})
        if r['split'] != games[r['game_id']]['split'] or r['split'] not in ('train', 'validation', 'test'):
            raise ValueError('game split mismatch')
        if r['label'] != {'1-0': 1., '0-1': 0., '1/2-1/2': .5}[games[r['game_id']]['result']]:
            raise ValueError('game label mismatch')
    return rows, m


def arrays(rows, split):
    selected = [r for r in rows if r['split'] == split]
    x, y = check_arrays([r['features'] for r in selected], [r['label'] for r in selected])
    return selected, x, y


def validate_model_manifest(path):
    path = Path(path)
    m = json.loads(path.read_text())
    schema = json.loads((ROOT/'schemas/linear-model-v1.schema.json').read_text())
    validate_record(m, schema)
    weights = load_model(path.parent/m['model_file'], m['model_sha256'])
    if weights != m['weights']:
        raise ValueError('manifest/model weights mismatch')
    return m


class LinearTrainer:
    def __init__(self, feature_manifest):
        self.feature_manifest = str(feature_manifest)

    def fit(self, spec: TrainingSpec, output_directory: str) -> str:
        rows, provenance = read_features(self.feature_manifest, spec)
        output = Path(output_directory)
        output.mkdir(parents=True, exist_ok=False)
        _, train_x, train_y = arrays(rows, 'train')
        _, val_x, val_y = arrays(rows, 'validation')
        candidates = []
        for penalty in LAMBDAS:
            result = optimize(train_x, train_y, penalty)
            result['train'] = metrics(train_x, train_y, result['weights'])
            result['validation'] = metrics(val_x, val_y, result['weights'])
            candidates.append(result)
        selection = {'spec': asdict(spec), 'feature_manifest': self.feature_manifest,
                     'feature_provenance': provenance, 'candidates': candidates,
                     'handcrafted': {'train': metrics(train_x, train_y, WEIGHTS),
                                     'validation': metrics(val_x, val_y, WEIGHTS)}}
        write_json(output/'selection.json', selection)
        if not all(r['success'] for r in candidates):
            raise ValueError('optimizer failed; see retained selection.json')
        chosen = min((r for r in candidates if r['lambda'] > 0), key=lambda r: (r['validation']['bce'], -r['lambda']))
        text = encode_model(chosen['weights'], sha256(spec.dataset_manifest), sha256(spec.split_manifest))
        (output/'model.txt').write_bytes(text.encode('ascii'))
        manifest = {'schema_version': 1, 'kind': 'ucl-linear-model', 'status': 'frozen',
                    'feature_version': VERSION, 'perspective': 'white', 'temperature': TAU,
                    'intercept': 0, 'weights': chosen['weights'], 'lambda': chosen['lambda'], 'seed': spec.seed,
                    'model_file': 'model.txt', 'model_sha256': sha256(output/'model.txt'),
                    'dataset_sha256': sha256(spec.dataset_manifest), 'split_sha256': sha256(spec.split_manifest),
                    'features_sha256': provenance['features_sha256'], 'selection_sha256': sha256(output/'selection.json'),
                    'code': git_state(ROOT), 'environment': {**hardware(), 'numpy': np.__version__,
                        'scipy': importlib.metadata.version('scipy'), 'numpy_config': str(np.show_config(mode='dicts'))},
                    'training_spec': asdict(spec), 'configuration': {'lambdas': LAMBDAS, 'loss': 'fractional-BCE',
                        'penalty': 'lambda/2 * ||w*train_RMS/400 - w_handcrafted*train_RMS/400||^2',
                        'intercept': 0, 'scaling': 'train-only RMS; no centering; raw deploy weights',
                        'optimizer': 'L-BFGS-B', 'maxiter': 1000, 'gtol': 1e-9, 'ftol': 1e-12}}
        write_json(output/'model-manifest.json', manifest)
        validate_model_manifest(output/'model-manifest.json')
        return str(output/'model-manifest.json')


def evaluate_frozen(manifest_path, feature_manifest):
    """One official test operation, only after selection/model freeze; never refit here."""
    manifest_path = Path(manifest_path)
    m = validate_model_manifest(manifest_path)
    output = manifest_path.parent
    selection = json.loads((output/'selection.json').read_text())
    if sha256(output/'selection.json') != m['selection_sha256']:
        raise ValueError('selection integrity mismatch')
    spec = TrainingSpec(**m['training_spec'])
    rows, _ = read_features(feature_manifest, spec)
    selected, x, y = arrays(rows, 'test')
    models = {'handcrafted': WEIGHTS, 'unregularized': selection['candidates'][0]['weights'], 'regularized': m['weights']}
    # Exclusive marker prevents accidental re-opening the frozen test procedure.
    with (output/'test-evaluation.started.json').open('x') as stream:
        json.dump({'model_sha256': m['model_sha256'], 'features_sha256': m['features_sha256'],
                   'test_position_ids_sha256': __import__('hashlib').sha256('\n'.join(r['position_id'] for r in selected).encode()).hexdigest()}, stream)
    result = {'model_sha256': m['model_sha256'], 'test_games': len({r['game_id'] for r in selected}),
              'models': {name: metrics(x, y, w) for name, w in models.items()}, 'strata': {}}
    for name, predicate in {'white_to_move': lambda r: r['fen'].split()[1] == 'w',
                            'black_to_move': lambda r: r['fen'].split()[1] == 'b',
                            'early_ply16_40': lambda r: r['ply'] <= 40,
                            'later_ply48_160': lambda r: r['ply'] > 40,
                            'draw_label': lambda r: r['label'] == .5,
                            'decisive_label': lambda r: r['label'] != .5}.items():
        idx = [i for i, r in enumerate(selected) if predicate(r)]
        result['strata'][name] = {n: metrics(x[idx], y[idx], w) for n,w in models.items()} if idx else {}
    # Whole games are independent bootstrap clusters; all their positions travel together.
    gids = sorted({r['game_id'] for r in selected})
    counts = np.array([sum(r['game_id'] == g for r in selected) for g in gids])
    z0 = x @ np.asarray(WEIGHTS) / TAU
    losses0 = np.logaddexp(0., z0)-y*z0
    rng = np.random.default_rng(spec.seed)
    indices = rng.integers(0, len(gids), size=(2000, len(gids)))
    result['game_cluster_bootstrap'] = {'seed': spec.seed, 'resamples': 2000, 'unit': 'game', 'differences': {}}
    for name in ('unregularized', 'regularized'):
        z = x @ np.asarray(models[name]) / TAU
        losses = np.logaddexp(0., z)-y*z
        differences = {}
        for metric, delta in {'bce': losses-losses0, 'brier': (expit(z)-y)**2-(expit(z0)-y)**2}.items():
            sums = np.array([sum(delta[i] for i,r in enumerate(selected) if r['game_id'] == g) for g in gids])
            boot = sums[indices].sum(axis=1)/counts[indices].sum(axis=1)
            differences[metric] = {'difference': float(np.mean(delta)), 'ci95': np.quantile(boot, [.025,.975]).tolist()}
        result['game_cluster_bootstrap']['differences'][name] = differences
    write_json(output/'test-results.json', result)
    return result

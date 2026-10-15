"""Strict portable linear deployment format shared with the C++ loader."""
import math
from pathlib import Path
import re

from .records import sha256


def encode_model(weights, dataset_hash, split_hash):
    if len(weights) != 8 or any(type(w) not in (float, int) or not math.isfinite(w) or abs(w) > 10000 for w in weights):
        raise ValueError('invalid model weights')
    if any(not re.fullmatch('[0-9a-f]{64}', h) for h in (dataset_hash, split_hash)):
        raise ValueError('invalid model provenance hash')
    return ('ucl-linear-v1\nfeatures handcrafted-v1\nperspective white\ntemperature 400\nintercept 0\nweights 8 '
            + ' '.join(format(w, '.17g') for w in weights)
            + f'\ndataset_sha256 {dataset_hash}\nsplit_sha256 {split_hash}\nend\n')


def load_model(path, expected_sha256):
    path = Path(path)
    if not re.fullmatch('[0-9a-f]{64}', expected_sha256) or sha256(path) != expected_sha256:
        raise ValueError('model SHA-256 mismatch')
    if path.stat().st_size > 4096:
        raise ValueError('model exceeds size limit')
    tokens = path.read_text(encoding='ascii').split()
    if (len(tokens) != 24 or tokens[:11] != ['ucl-linear-v1', 'features', 'handcrafted-v1',
            'perspective', 'white', 'temperature', '400', 'intercept', '0', 'weights', '8']):
        raise ValueError('model schema/version mismatch')
    # 11 prefix tokens, 8 weights, two hash pairs and one terminator = 24.
    weights = [float(t) for t in tokens[11:19]]
    if tokens[19] != 'dataset_sha256' or tokens[21] != 'split_sha256' or tokens[23:] != ['end']:
        raise ValueError('model schema mismatch')
    encode_model(weights, tokens[20], tokens[22])
    return weights

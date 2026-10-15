"""Strict portable linear deployment format shared with the C++ loader."""
import math
from pathlib import Path
import re

from .records import sha256


def encode_model(weights, dataset_hash, split_hash):
    if len(weights) not in (8,14) or any(type(w) not in (float, int) or not math.isfinite(w) or abs(w) > 10000 for w in weights):
        raise ValueError('invalid model weights')
    if any(not re.fullmatch('[0-9a-f]{64}', h) for h in (dataset_hash, split_hash)):
        raise ValueError('invalid model provenance hash')
    version,features = ('ucl-linear-v1','handcrafted-v1') if len(weights)==8 else ('ucl-linear-v2','interpretable-v2')
    return (f'{version}\nfeatures {features}\nperspective white\ntemperature 400\nintercept 0\nweights {len(weights)} '
            + ' '.join(format(w, '.17g') for w in weights)
            + f'\ndataset_sha256 {dataset_hash}\nsplit_sha256 {split_hash}\nend\n')


def load_model(path, expected_sha256):
    path = Path(path)
    if not re.fullmatch('[0-9a-f]{64}', expected_sha256) or sha256(path) != expected_sha256:
        raise ValueError('model SHA-256 mismatch')
    if path.stat().st_size > 4096:
        raise ValueError('model exceeds size limit')
    tokens = path.read_text(encoding='ascii').split()
    n = 14 if tokens[:3] == ['ucl-linear-v2','features','interpretable-v2'] else 8
    prefix = ['ucl-linear-v2' if n==14 else 'ucl-linear-v1', 'features',
              'interpretable-v2' if n==14 else 'handcrafted-v1', 'perspective','white',
              'temperature','400','intercept','0','weights',str(n)]
    if len(tokens)!=n+16 or tokens[:11]!=prefix:
        raise ValueError('model schema/version mismatch')
    weights=[float(t) for t in tokens[11:11+n]]
    if tokens[11+n]!='dataset_sha256' or tokens[13+n]!='split_sha256' or tokens[15+n:]!=['end']:
        raise ValueError('model schema mismatch')
    encode_model(weights,tokens[12+n],tokens[14+n])
    return weights

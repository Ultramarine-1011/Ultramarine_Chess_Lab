"""C++ feature export is the training input; Python reference is an independent check."""
import gzip
import json
import math
from pathlib import Path
import subprocess

import chess

from .dataset import validate_dataset, write_gzip
from .records import sha256, write_json

VERSION = 'handcrafted-v1'
WEIGHTS = [100, 320, 330, 500, 900, 5, 4, 30]


def reference_features(board):
    result = [0.] * 8
    for color, sign in ((chess.WHITE, 1), (chess.BLACK, -1)):
        for i, piece in enumerate((chess.PAWN, chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN)):
            result[i] += sign * len(board.pieces(piece, color))
        for sq in board.pieces(chess.PAWN, color):
            rank = chess.square_rank(sq) if color else 7 - chess.square_rank(sq)
            result[5] += sign * (rank - 1)
        for sq in board.pieces(chess.KNIGHT, color) | board.pieces(chess.BISHOP, color):
            file, rank = chess.square_file(sq), chess.square_rank(sq)
            result[6] += sign * (min(file, 7-file) + min(rank, 7-rank))
        result[7] += sign * (len(board.pieces(chess.BISHOP, color)) >= 2)
    return result


def validate_vector(record):
    if set(record) != {'feature_version', 'features', 'handcrafted_cp'} or record['feature_version'] != VERSION:
        raise ValueError('feature version/schema mismatch')
    x = record['features']
    if len(x) != 8 or not all(type(v) in (float, int) and math.isfinite(v) for v in x):
        raise ValueError('invalid feature dimension/value')
    if type(record['handcrafted_cp']) is not int:
        raise ValueError('invalid handcrafted score')


def extract(engine, fens):
    p = subprocess.run([str(Path(engine).resolve()), '--features'], input='\n'.join(fens)+'\n',
                       text=True, capture_output=True, timeout=60, check=True)
    records = [json.loads(line) for line in p.stdout.splitlines()]
    if len(records) != len(fens):
        raise ValueError('C++ export row count mismatch')
    for fen, record in zip(fens, records, strict=True):
        validate_vector(record)
        b = chess.Board(fen)
        expected = reference_features(b)
        if record['features'] != expected:
            raise ValueError('Python/C++ feature mismatch')
        cp = sum(w*x for w, x in zip(WEIGHTS, expected, strict=True)) * (1 if b.turn else -1)
        if record['handcrafted_cp'] != cp:
            raise ValueError('handcrafted weight reproduction mismatch')
    return records


def export_dataset(dataset, engine, output, feature_version=VERSION):
    dataset, output = Path(dataset), Path(output)
    kind = json.loads((dataset / 'manifest.json').read_text())['kind']
    if kind == 'r4-dataset':
        from .r4_data import validate_dataset as validate_r4
        validate_r4(dataset)
    else:
        validate_dataset(dataset)
    rows = [json.loads(line) for line in gzip.decompress((dataset / 'positions.jsonl.gz').read_bytes()).decode().splitlines()]
    if feature_version == VERSION:
        features = extract(engine, [r['fen'] for r in rows])
    elif feature_version == 'interpretable-v2':
        from .r4_features import extract as extract_v2
        features = extract_v2(engine, [r['fen'] for r in rows])
    else:
        raise ValueError('unsupported export version')
    for row, feature in zip(rows, features, strict=True):
        row.update(feature_version=feature['feature_version'], features=feature['features'], handcrafted_cp=feature['handcrafted_cp'])
    output.mkdir(parents=True, exist_ok=False)
    write_gzip(output / 'features.jsonl.gz', ''.join(json.dumps(r, sort_keys=True)+'\n' for r in rows))
    info = json.loads(subprocess.check_output([str(Path(engine).resolve()), '--build-info'], text=True))
    manifest = {'schema_version': 1, 'feature_version': feature_version, 'count': len(rows),
                'dataset_manifest_sha256': sha256(dataset / 'manifest.json'),
                'positions_sha256': sha256(dataset / 'positions.jsonl.gz'),
                'splits_sha256': sha256(dataset / 'splits.json'),
                'features_sha256': sha256(output / 'features.jsonl.gz'),
                'engine_sha256': sha256(engine), 'build_info': info,
                'consistency': 'all rows exactly equal independent Python extraction and handcrafted score'}
    write_json(output / 'manifest.json', manifest)
    return manifest

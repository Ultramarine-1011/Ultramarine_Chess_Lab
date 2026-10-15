"""R5 independent openings; reuse the bounded R4 source and legal PGN pipeline."""
import argparse
import gzip
import io
import json
from pathlib import Path

import chess
import chess.pgn

from .dataset import digest, position_key, prepare, write_gzip
from .r4_data import bounded_source
from .records import git_state, sha256, write_json

SEED = 20261016
ROOT = Path(__file__).resolve().parents[2]
EXCLUSIONS = (
    'experiments/openings/r3-v1.json',
    'experiments/results/r4-openings-v1/positions.json',
    'experiments/results/r3-data-v1/positions.jsonl.gz',
    'experiments/results/r3-data-v1/splits.json',
    'experiments/results/r3-data-v1/source.pgn.gz',
    'experiments/results/r3-data-v2/positions.jsonl.gz',
    'experiments/results/r3-data-v2/splits.json',
    'experiments/results/r3-data-v2/source.pgn.gz',
    'experiments/results/r4-data-v1/positions.jsonl.gz',
    'experiments/results/r4-data-v1/splits.json',
    'experiments/results/r4-data-v1/source.pgn.gz',
)


def exclusions():
    keys, games, sites = set(), set(), set()
    for name in EXCLUSIONS:
        path = ROOT / name
        if name.endswith('positions.jsonl.gz'):
            keys.update(json.loads(line)['position_id'] for line in gzip.decompress(path.read_bytes()).decode().splitlines())
        elif name.endswith('splits.json'):
            games.update(json.loads(path.read_text(encoding='utf-8')))
        elif name.endswith('source.pgn.gz'):
            stream = io.StringIO(gzip.decompress(path.read_bytes()).decode())
            while (game := chess.pgn.read_game(stream)) is not None:
                if game.errors:
                    raise ValueError('invalid retained exclusion source')
                sites.add(game.headers.get('Site'))
                board = game.board()
                moves = list(game.mainline_moves())
                games.add(digest(board.fen() + ' ' + ' '.join(m.uci() for m in moves)))
                for ply, move in enumerate(moves[:12], 1):
                    board.push(move)
                    if ply == 12:
                        keys.add(position_key(board))
        else:
            data = json.loads(path.read_text(encoding='utf-8'))
            for p in data['positions'] if isinstance(data, dict) else data:
                keys.add(position_key(chess.Board(p['fen'])))
    return keys, games, sites


def select(text, excluded):
    keys, old_games, sites = excluded
    _, games, counts = prepare(text, seed=SEED, metadata=True, opening_plies=12)
    seen, selected = set(keys), []
    for gid in sorted(games, key=lambda g: digest(f'{SEED}:{g}')):
        g = games[gid]
        if gid in old_games or g['site'] in sites or 'opening_fen' not in g:
            continue
        board = chess.Board(g['opening_fen'])
        key = position_key(board)
        if key in seen:
            continue
        seen.add(key)
        selected.append({'id': f'r5-{len(selected)+1:03}', 'game_id': gid,
                         'site': g['site'], 'utc': g['utc'], 'eco': g['eco'],
                         'fen': board.fen(), 'moves': g['opening_moves'], 'position_id': key})
        if len(selected) == 200:
            break
    return selected, counts


def acquire(output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    text, source = bounded_source('2017-09', ROOT / '.tools/r5-sources')
    positions, counts = select(text, exclusions())
    write_gzip(output / 'source.pgn.gz', text)
    write_json(output / 'positions.json', positions)
    (output / 'openings.epd').write_text(''.join(chess.Board(p['fen']).epd(id=p['id'])+'\n' for p in positions), encoding='utf-8', newline='\n')
    manifest = {'kind': 'r5-independent-openings', 'code': git_state(ROOT), 'source': source,
                'seed': SEED, 'positions': len(positions), 'target': 200, 'filter_counts': counts,
                'status': 'PASS' if len(positions) == 200 else 'BLOCKED_INPUT',
                'exclusions': {n: sha256(ROOT/n) for n in EXCLUSIONS},
                'protocol_sha256': sha256(ROOT/'docs/r5/protocol.md'),
                'files': {p.name: {'sha256': sha256(p), 'bytes': p.stat().st_size} for p in output.iterdir()}}
    write_json(output / 'manifest.json', manifest)
    return manifest


def validate(output):
    output = Path(output)
    m = json.loads((output/'manifest.json').read_text(encoding='utf-8'))
    for n, h in m['exclusions'].items():
        if sha256(ROOT/n) != h:
            raise ValueError('exclusion identity changed: '+n)
    for n, meta in m['files'].items():
        if Path(n).name != n or sha256(output/n) != meta['sha256'] or (output/n).stat().st_size != meta['bytes']:
            raise ValueError('opening artifact integrity mismatch')
    positions, counts = select(gzip.decompress((output/'source.pgn.gz').read_bytes()).decode(), exclusions())
    if positions != json.loads((output/'positions.json').read_text()) or counts != m['filter_counts']:
        raise ValueError('opening reconstruction mismatch')
    expected = ''.join(chess.Board(p['fen']).epd(id=p['id'])+'\n' for p in positions)
    if expected != (output/'openings.epd').read_text() or len(positions) != 200:
        raise ValueError('opening EPD/count mismatch')
    return m


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=['acquire', 'validate'])
    parser.add_argument('--output', default='experiments/results/r5-openings-v1')
    args = parser.parse_args()
    print(json.dumps((acquire if args.operation == 'acquire' else validate)(args.output), indent=2))

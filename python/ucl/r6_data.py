"""R6 bounded real data, paired labels and independent legal-child teacher queries."""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import gzip
import io
import json
from pathlib import Path
import subprocess
import time

import chess
import chess.engine
import chess.pgn
from scipy.special import expit

from .dataset import digest, position_key, prepare, write_gzip
from .r4_data import annotated, bounded_source, diagnostics
from .r4_features import extract
from .r5_openings import exclusions
from .records import git_state, hardware, sha256, write_json

ROOT = Path(__file__).resolve().parents[2]
SEED = 20261016
NODES = 20000
MONTHS = ('2018-01', '2018-02', '2018-03', '2018-04')
CAPS = {'train': 14000, 'validation': 3500, 'test': 6500}
OPTIONS = {'Threads': 1, 'Hash': 16, 'Skill Level': 20,
           'UCI_LimitStrength': False, 'UCI_ShowWDL': True, 'SyzygyPath': ''}


def read_rows(path):
    return [json.loads(s) for s in gzip.decompress(Path(path).read_bytes()).decode().splitlines()]


def save_rows(path, rows):
    write_gzip(path, ''.join(json.dumps(r, sort_keys=True)+'\n' for r in rows))


def split(headers, gid):
    if headers['UCLSourceMonth'] == MONTHS[-1]:
        return 'test'
    return 'train' if int(digest(f'{SEED}:{gid}')[:8], 16) % 100 < 80 else 'validation'


def old_exclusions():
    keys, games, sites = exclusions()
    d = ROOT/'experiments/results/r5-openings-v1'
    for p in json.loads((d/'positions.json').read_text(encoding='utf-8')):
        keys.add(position_key(chess.Board(p['fen'])))
        games.add(p['game_id'])
        sites.add(p['site'])
    source_exclusions(gzip.decompress((d/'source.pgn.gz').read_bytes()).decode(), keys, games, sites)
    return keys, games, sites


def source_exclusions(text, keys, games, sites):
    stream = io.StringIO(text)
    while (g := chess.pgn.read_game(stream)) is not None:
        if g.errors:
            raise ValueError('invalid exclusion PGN')
        b = g.board()
        moves = list(g.mainline_moves())
        games.add(digest(b.fen()+' '+' '.join(m.uci() for m in moves)))
        sites.add(g.headers.get('Site'))
        for m in moves[:12]:
            b.push(m)
        if len(moves) >= 12:
            keys.add(position_key(b))


def select_data(text, excluded):
    rows, games, counts = prepare(text, seed=SEED, split_resolver=split, metadata=True)
    keys, old_games, sites = excluded
    rows = [r for r in rows if r['position_id'] not in keys and r['game_id'] not in old_games
            and games[r['game_id']]['site'] not in sites]
    by_game = {}
    for r in rows:
        by_game.setdefault(r['game_id'], []).append(r)
    kept, selected, totals = {}, [], Counter()
    for gid in sorted(by_game, key=lambda g: digest(f'{SEED}:{g}')):
        group = by_game[gid]
        s = games[gid]['split']
        if totals[s]+len(group) <= CAPS[s]:
            kept[gid] = games[gid]
            selected.extend(group)
            totals[s] += len(group)
    selected.sort(key=lambda r: (r['game_id'], r['ply']))
    counts['r6_retained'] = len(selected)
    counts['r6_games'] = len(kept)
    return selected, kept, counts


def select_openings(text, excluded):
    keys, games, sites = excluded
    _, candidates, counts = prepare(text, seed=SEED, metadata=True, opening_plies=12)
    selected, seen = [], set(keys)
    for gid in sorted(candidates, key=lambda g: digest(f'{SEED}:{g}')):
        g = candidates[gid]
        if gid in games or g['site'] in sites or 'opening_fen' not in g:
            continue
        key = position_key(chess.Board(g['opening_fen']))
        if key in seen:
            continue
        seen.add(key)
        selected.append({'id': f'r6-{len(selected)+1:03}', 'game_id': gid,
                         'position_id': key, **g})
        if len(selected) == 200:
            break
    if len(selected) != 200:
        raise ValueError('insufficient independent openings')
    return selected, counts


def acquire(output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    sources, texts = [], []
    for month in (*MONTHS, '2018-05'):
        text, meta = bounded_source(month, ROOT/'.tools/r6-sources')
        write_gzip(output/f'source-{month}.pgn.gz', text)
        sources.append(meta)
        texts.append(annotated(text, month))
        print(f'{month}: bounded source retained', flush=True)
    combined = ''.join(texts[:4])
    excluded = old_exclusions()
    rows, games, counts = select_data(combined, excluded)
    opening_excluded = tuple(set(s) for s in excluded)
    for text in texts[:4]:
        source_exclusions(text, *opening_excluded)
    opening_excluded[0].update(r['position_id'] for r in rows)
    openings, opening_counts = select_openings(texts[4], opening_excluded)
    opening_keys = {r['position_id'] for r in openings}
    if any(r['position_id'] in opening_keys for r in rows):
        raise ValueError('training/opening leak')
    save_rows(output/'positions.jsonl.gz', rows)
    write_json(output/'splits.json', games)
    write_json(output/'openings.json', openings)
    (output/'openings.epd').write_text(''.join(chess.Board(p['opening_fen']).epd(id=p['id'])+'\n'
                                              for p in openings), encoding='utf-8', newline='\n')
    write_json(output/'diagnostics.json', diagnostics(rows, games))
    m = {'kind': 'r6-dataset', 'seed': SEED, 'sources': sources, 'caps': CAPS,
         'counts': counts, 'opening_counts': opening_counts, 'code': git_state(ROOT),
         'protocol_sha256': sha256(ROOT/'docs/r6/protocol.md'),
         'files': {p.name: {'sha256': sha256(p), 'bytes': p.stat().st_size} for p in output.iterdir()}}
    write_json(output/'manifest.json', m)
    return m


def validate(output):
    d = Path(output)
    m = json.loads((d/'manifest.json').read_text(encoding='utf-8'))
    for name, meta in m['files'].items():
        if Path(name).name != name or sha256(d/name) != meta['sha256']:
            raise ValueError('dataset artifact mismatch')
    texts = [annotated(gzip.decompress((d/f'source-{month}.pgn.gz').read_bytes()).decode(), month)
             for month in (*MONTHS, '2018-05')]
    excluded = old_exclusions()
    rows, games, counts = select_data(''.join(texts[:4]), excluded)
    if rows != read_rows(d/'positions.jsonl.gz') or games != json.loads((d/'splits.json').read_text(encoding='utf-8')) or counts != m['counts']:
        raise ValueError('dataset reconstruction mismatch')
    for text in texts[:4]:
        source_exclusions(text, *excluded)
    excluded[0].update(r['position_id'] for r in rows)
    openings, counts = select_openings(texts[4], excluded)
    if openings != json.loads((d/'openings.json').read_text(encoding='utf-8')) or counts != m['opening_counts']:
        raise ValueError('opening reconstruction mismatch')
    return {'status': 'PASS', 'positions': len(rows), 'games': len(games), 'openings': len(openings)}


def teacher_record(board, info=None):
    outcome = board.outcome(claim_draw=True)
    if outcome:
        target = .5 if outcome.winner is None else float(outcome.winner)
        order = 0 if target == .5 else (100000 if target else -100000)
        return {'kind': 'terminal', 'termination': outcome.termination.name,
                'white_cp': None, 'white_mate': None, 'white_order': order,
                'target': target, 'nodes': 0, 'depth': 0, 'pv': []}
    if not info or 'score' not in info or info.get('upperbound') or info.get('lowerbound'):
        raise ValueError('missing or bound teacher score')
    white, stm = info['score'].white(), info['score'].pov(board.turn)
    cp, mate = white.score(), white.mate()
    if cp is None and mate is None or cp is not None and not -100000 < cp < 100000:
        raise ValueError('invalid teacher score')
    target = float(white > chess.engine.Cp(0)) if white.is_mate() else float(expit(max(-2000, min(2000, cp))/400))
    pv = [move.uci() for move in info.get('pv', [])]
    check = board.copy()
    for move in pv:
        check.push_uci(move)
    return {'kind': 'mate' if white.is_mate() else 'cp', 'white_cp': cp, 'white_mate': mate,
            'stm_cp': stm.score(), 'stm_mate': stm.mate(), 'perspective': 'white',
            'white_order': white.score(mate_score=100000), 'target': target,
            'nodes': info.get('nodes'), 'depth': info.get('depth'), 'pv': pv,
            'wdl_white': list(info['wdl'].white()) if 'wdl' in info else None}


def query(client, fen):
    b = chess.Board(fen)
    if not b.is_valid():
        raise ValueError('illegal teacher input')
    if b.outcome(claim_draw=True):
        return teacher_record(b)
    exact, final_nodes = None, None
    with client.analysis(b, chess.engine.Limit(nodes=NODES), game=object(), info=chess.engine.INFO_ALL) as analysis:
        for info in analysis:
            final_nodes = info.get('nodes', final_nodes)
            if 'score' in info and not info.get('upperbound') and not info.get('lowerbound'):
                exact = info
        analysis.wait()
    result = teacher_record(b, exact)
    result['final_nodes'] = final_nodes
    return result


def label(engine, output, rows, workers=4):
    """Append completed rows for interruption recovery; reject incompatible reuse."""
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    identity = {'sha256': sha256(engine), 'requested_nodes': NODES, 'options': OPTIONS,
                'perspective': 'white', 'cold_hash': True}
    identity_path = output/'teacher.json'
    if identity_path.exists() and json.loads(identity_path.read_text(encoding='utf-8')) != identity:
        raise ValueError('teacher identity changed')
    write_json(identity_path, identity)
    manifest_path = output/'manifest.json'
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        existing = read_rows(output/'labels.jsonl.gz')
        if sha256(output/'labels.jsonl.gz') != manifest['sha256'] or len(existing) != len(rows):
            raise ValueError('completed label integrity mismatch')
        for expected_row, actual in zip(rows, existing, strict=True):
            if any(actual.get(k) != v for k, v in expected_row.items()):
                raise ValueError('completed label input mismatch')
        return existing
    journal = output/'completed.jsonl'
    done = {}
    if journal.exists():
        for line in journal.read_text(encoding='utf-8').splitlines():
            r = json.loads(line)
            if r['position_id'] in done:
                raise ValueError('duplicate journal identity')
            done[r['position_id']] = r
    expected = {r['position_id']: r for r in rows}
    for pid, r in done.items():
        if pid not in expected or any(r[k] != v for k, v in expected[pid].items()):
            raise ValueError('journal input mismatch')
    pending = [r for r in rows if r['position_id'] not in done]
    start = time.monotonic()
    def batch(chunk):
        with chess.engine.SimpleEngine.popen_uci(str(Path(engine).resolve()), timeout=60) as client:
            if client.id.get('name') != 'Stockfish 17.1':
                raise ValueError('unexpected teacher version')
            client.configure(OPTIONS)
            return [{**r, 'teacher_evaluation': query(client, r['fen'])} for r in chunk]
    # Bounded batches allow useful durable progress without one file per label.
    chunks = [pending[i:i+32] for i in range(0, len(pending), 32)]
    with ThreadPoolExecutor(max_workers=workers) as pool, journal.open('a', encoding='utf-8', newline='\n') as stream:
        for chunk in pool.map(batch, chunks):
            for r in chunk:
                stream.write(json.dumps(r, sort_keys=True)+'\n')
                done[r['position_id']] = r
            stream.flush()
            if len(done) % 512 < 32:
                print(f'labels {len(done)}/{len(rows)}; {time.monotonic()-start:.1f}s', flush=True)
    result = [done[r['position_id']] for r in rows]
    save_rows(output/'labels.jsonl.gz', result)
    write_json(output/'manifest.json', {'teacher': identity, 'rows': len(result),
               'sha256': sha256(output/'labels.jsonl.gz'), 'seconds_this_run': time.monotonic()-start,
               'code': git_state(ROOT), 'hardware': hardware(),
               'score_kinds': dict(Counter(r['teacher_evaluation']['kind'] for r in result))})
    return result


def features(dataset, engine, output):
    d, output = Path(dataset), Path(output)
    rows = read_rows(d/'positions.jsonl.gz')
    fs = extract(engine, [r['fen'] for r in rows])
    games = json.loads((d/'splits.json').read_text(encoding='utf-8'))
    for r, f in zip(rows, fs, strict=True):
        r.update(f)
        r.update(game_result=r['label'], source=games[r['game_id']])
    output.mkdir(parents=True, exist_ok=False)
    save_rows(output/'features.jsonl.gz', rows)
    write_json(output/'manifest.json', {'positions': len(rows), 'feature_version': 'interpretable-v2',
               'sha256': sha256(output/'features.jsonl.gz'), 'dataset_sha256': sha256(d/'manifest.json'),
               'engine_sha256': sha256(engine), 'all_cpp_python_exact': True})
    return rows


def ranking_rows(rows, which):
    roots = sorted([r for r in rows if r['split'] == which],
                   key=lambda r: digest(f'{SEED}:{r["position_id"]}'))[:128]
    children = []
    for r in roots:
        board = chess.Board(r['fen'])
        for move in sorted(board.legal_moves, key=lambda m: m.uci()):
            child = board.copy()
            child.push(move)
            children.append({'position_id': digest(r['position_id']+':'+move.uci()),
                             'root_id': r['position_id'], 'game_id': r['game_id'], 'split': which,
                             'root_turn': board.turn, 'move': move.uci(), 'fen': child.fen()})
    return children


def preflight(input_path, teacher, engine, output):
    import numpy as np
    from .model import encode_model
    from .r4_training import arrays, optimize
    rows = [r for r in read_rows(input_path) if r['split'] == 'train'][:256]
    start = time.monotonic()
    labeled = label(teacher, output, rows)
    with chess.engine.SimpleEngine.popen_uci(str(Path(teacher).resolve())) as client:
        client.configure(OPTIONS)
        for r in labeled[:8]:
            if query(client, r['fen']) != r['teacher_evaluation']:
                raise ValueError('cold-hash teacher not reproducible')
    for r in labeled:
        e = r['teacher_evaluation']
        if e['kind'] == 'cp' and e['white_cp'] != e['stm_cp']*(1 if chess.Board(r['fen']).turn else -1):
            raise ValueError('teacher perspective inconsistency')
    _, x, y, q = arrays(labeled, 'train')
    t = np.asarray([r['teacher_evaluation']['target'] for r in labeled])
    fits = {}
    for name, target in [('G', y), ('T', t), ('M', .8*t+.2*y)]:
        fit = optimize(x, target, q, list(range(14)), .01)
        if not fit['success']:
            raise ValueError('pilot optimizer failed')
        model = Path(output)/f'pilot-{name}.txt'
        model.write_bytes(encode_model(fit['weights'], '0'*64, '0'*64).encode('ascii'))
        proc = subprocess.run([str(Path(engine).resolve()), '--infer', str(model.resolve()), sha256(model)],
                              input='\n'.join(r['fen'] for r in labeled)+'\n', text=True, capture_output=True, check=True)
        actual = [json.loads(s) for s in proc.stdout.splitlines()]
        for r, out in zip(labeled, actual, strict=True):
            white = sum(a*b for a, b in zip(r['features'], fit['weights'], strict=True))
            if not np.isclose(out['white_score'], white, rtol=1e-13, atol=1e-9):
                raise ValueError('pilot C++ inference mismatch')
        fits[name] = {'success': fit['success'], 'lambda': .01, 'model_sha256': sha256(model)}
    summary = {'status': 'PASS', 'positions': len(labeled), 'features': 'all dataset C++/Python exact',
               'perspectives': dict(Counter(r['fen'].split()[1] for r in labeled)),
               'repeated_queries_exact': 8, 'fits_and_deployment': fits,
               'seconds': time.monotonic()-start, 'formal_positions': 23998,
               'formal_decision': 'retain registered caps, 20000 nodes and four workers',
               'pilot_scope': 'training split only; optimizer/deployment smoke, no model selection'}
    write_json(Path(output)/'preflight.json', summary)
    return summary


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('operation', choices=['acquire', 'validate', 'features', 'preflight', 'label', 'rank'])
    p.add_argument('--output', required=True)
    p.add_argument('--input')
    p.add_argument('--engine')
    p.add_argument('--feature-engine', default='build/release/ucl.exe')
    p.add_argument('--split', choices=['train', 'validation', 'test'])
    p.add_argument('--limit', type=int)
    a = p.parse_args()
    if a.operation == 'acquire':
        print(json.dumps(acquire(a.output)['counts'], indent=2))
    elif a.operation == 'validate':
        print(validate(a.output))
    elif a.operation == 'features':
        print(len(features(a.input, a.engine, a.output)))
    elif a.operation == 'preflight':
        print(preflight(a.input, a.engine, a.feature_engine, a.output))
    else:
        rows = read_rows(a.input)
        if a.operation == 'rank':
            rows = ranking_rows(rows, a.split)
        elif a.split:
            rows = [r for r in rows if r['split'] == a.split]
        if a.limit:
            rows = rows[:a.limit]
        result = label(a.engine, a.output, rows)
        if a.operation == 'rank':
            fs = extract(a.feature_engine, [r['fen'] for r in result])
            for r, f in zip(result, fs, strict=True):
                r.update(features=f['features'])
            save_rows(Path(a.output)/'children.jsonl.gz', result)
        print(f'completed {len(result)} rows')

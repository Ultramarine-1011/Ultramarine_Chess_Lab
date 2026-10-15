"""Exact frozen-corpus, seeded legal, boundary and deterministic-search comparison."""
import argparse
import gzip
import json
import logging
from pathlib import Path
import random
import struct
import subprocess

import chess
import chess.engine

from .benchmark import uci_score_cp
from .r4_features import reference
from .r5_study import ROOT, ORIGINAL, MODEL, MODEL_SHA, COMMON, SEED
from .match import runtime_options
from .records import git_state, sha256, write_json


def corpus():
    retained = [json.loads(line)['fen'] for line in gzip.decompress(
        (ROOT/'experiments/results/r4-data-v1/positions.jsonl.gz').read_bytes()).decode().splitlines()]
    if len(retained) != 44681:
        raise ValueError('frozen corpus size changed')
    rng, board, random_fens = random.Random(SEED), chess.Board(), []
    while len(random_fens) < 2048:
        if board.is_game_over(claim_draw=True) or board.ply() >= 180:
            board = chess.Board()
        board.push(rng.choice(list(board.legal_moves)))
        if board.ply() % 5 == 0:
            random_fens.append(board.fen())
    edges = [chess.STARTING_FEN,
        'r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1',
        '4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 1',
        '4k3/P7/8/8/8/8/8/4K3 w - - 0 1',
        '4k3/8/8/8/8/8/8/4K3 w - - 0 1',
        '4k3/8/8/2p5/2P1P3/P1P5/7P/4K3 w - - 0 1',
        '4k3/8/8/p7/P7/8/8/4K3 w - - 0 1',
        '7k/6Q1/6K1/8/8/8/8/8 b - - 100 1',
        '7k/5Q2/6K1/8/8/8/8/8 b - - 0 1',
        '4k3/8/8/8/8/8/4R3/4K3 b - - 99 1',
        'r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1']
    for start, moves in [(edges[1], ['e1g1', 'e8c8']), (edges[2], ['e5d6'])]:
        b = chess.Board(start)
        for move in moves:
            b.push_uci(move)
            edges.append(b.fen())
    for piece in 'qrbn':
        b = chess.Board(edges[3]); b.push_uci('a7a8'+piece); edges.append(b.fen())
    # Extra promoted pieces drive phase above 24 while retaining a legal board.
    edges.append('qqqqk3/8/8/8/8/8/8/QQQQK3 w - - 0 1')
    # This synthetic phase-boundary board is separately validated, not asserted reachable.
    extras = random_fens + edges
    for fen in extras:
        if not chess.Board(fen).is_valid():
            raise ValueError('invalid generated equivalence FEN: '+fen)
    mirrored = [chess.Board(fen).mirror().fen() for fen in extras]
    fens = retained + extras + mirrored
    search = json.loads((ROOT/'experiments/positions/r2-v1.json').read_text())['positions']
    search += [{'id': f'random-{i}', 'fen': fen} for i,fen in enumerate(random_fens[:32])]
    search += [{'id': f'edge-{i}', 'fen': fen} for i,fen in enumerate(edges)]
    return fens, search, {'retained': len(retained), 'random': len(random_fens), 'edges': len(edges), 'mirrors': len(mirrored)}


def exact(left, right):
    # JSON's 17-digit double representation round-trips the original binary64.
    return struct.pack('!d', float(left)) == struct.pack('!d', float(right))


def compare(candidate, output):
    output = Path(output); output.mkdir(parents=True, exist_ok=False)
    original = ROOT/f'.tools/engines/{ORIGINAL}/ucl.exe'
    candidate = Path(candidate).resolve()
    result = {'code': git_state(ROOT), 'status': 'running', 'binaries': {}, 'search_rows': [], 'error': None}
    logger = logging.getLogger('chess.engine')
    handler = logging.FileHandler(output/'search-uci.log', encoding='utf-8')
    old_level = logger.level; logger.addHandler(handler); logger.setLevel(logging.DEBUG)
    clients = []
    try:
        fens, cases, counts = corpus()
        result.update(corpus=counts, total_positions=len(fens))
        data = '\n'.join(fens)+'\n'
        (output/'positions.fen.gz').write_bytes(gzip.compress(data.encode(), mtime=0))
        exported = {}
        for name, binary in [('original', original), ('candidate', candidate)]:
            result['binaries'][name] = {'path': str(binary), 'sha256': sha256(binary),
                'build_info': json.loads(subprocess.check_output([str(binary), '--build-info'], text=True))}
            exported[name] = {}
            for mode, args in [('features', ['--features-v2']), ('inference', ['--infer', str(ROOT/MODEL), MODEL_SHA])]:
                run = subprocess.run([str(binary), *args], input=data, text=True, capture_output=True, timeout=180, check=True)
                (output/f'{name}-{mode}.jsonl.gz').write_bytes(gzip.compress(run.stdout.encode(), mtime=0))
                rows = [json.loads(line) for line in run.stdout.splitlines()]
                if len(rows) != len(fens): raise ValueError('export count mismatch')
                exported[name][mode] = rows
        for i, fen in enumerate(fens):
            a, b = (exported[n]['features'][i] for n in ('original', 'candidate'))
            x, y = (exported[n]['inference'][i] for n in ('original', 'candidate'))
            if a != b or x != y or not exact(x['white_score'], y['white_score']):
                raise ValueError(f'exact export mismatch at {i}: {fen}')
            if b['features'] != reference(chess.Board(fen)):
                raise ValueError(f'independent reference mismatch at {i}')
        result['features_and_inference_exact'] = True
        options = runtime_options(ROOT, {**COMMON, 'ModelSHA256': MODEL_SHA, 'ModelFile': MODEL, 'Evaluator': 'Linear'})
        for binary in (original, candidate):
            client = chess.engine.SimpleEngine.popen_uci(str(binary), timeout=120)
            client.configure(options); clients.append(client)
        for case in cases:
            for limit in ({'depth': 3}, {'depth': 4}, {'nodes': 50000}):
                rows = []
                for name, client in zip(('original', 'candidate'), clients):
                    board = chess.Board(case['fen'])
                    played = client.play(board, chess.engine.Limit(**limit), game=object(), info=chess.engine.INFO_ALL)
                    text = played.info.get('string', '')
                    if not text.startswith('ucl_stats '): raise ValueError('missing search counters')
                    native = json.loads(text[len('ucl_stats '):]); native.pop('elapsed_us')
                    pv = [m.uci() for m in played.info.get('pv', [])]
                    for move in pv: board.push_uci(move)
                    row = {'engine': name, 'case': case['id'], 'limit': limit,
                           'move': played.move.uci() if played.move else None, 'pv': pv, **native}
                    rows.append(row); result['search_rows'].append(row)
                if {k:v for k,v in rows[0].items() if k!='engine'} != {k:v for k,v in rows[1].items() if k!='engine'}:
                    raise ValueError('deterministic search mismatch: '+case['id']+' '+str(limit))
        if sha256(ROOT/MODEL) != MODEL_SHA: raise ValueError('frozen model changed')
        result.update(status='PASS', search_queries=len(result['search_rows']), search_cases=len(cases))
    except Exception as exc:
        result.update(status='FAIL', error=f'{type(exc).__name__}: {exc}')
    finally:
        for client in clients:
            try: client.quit()
            except chess.engine.EngineError: client.close()
        logger.removeHandler(handler); handler.close(); logger.setLevel(old_level)
        result['files'] = {p.name: {'sha256': sha256(p), 'bytes': p.stat().st_size} for p in output.iterdir() if p.is_file()}
        write_json(output/'record.json', result)
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--candidate', required=True); p.add_argument('--output', required=True)
    a = p.parse_args(); r = compare(a.candidate, a.output)
    print(r['status'], r['error'], r.get('total_positions'), r.get('search_queries'))
    raise SystemExit(r['status'] != 'PASS')

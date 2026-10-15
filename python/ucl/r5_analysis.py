"""Preregistered opening-paired statistics and exact PGN/UCI move correspondence."""
from collections import Counter, defaultdict
import gzip
import hashlib
import json
import math
from pathlib import Path
import random
import re
import statistics

import chess
import chess.pgn

from .integrity import validate_bundle
from .r4_results import analyze as analyze_r4, elo_equivalent
from .r5_study import ROOT, MODEL_SHA, SEED
from .records import git_state, sha256, write_json
from .report import CheckedGameBuilder, check_game_result


def bootstrap(means):
    if not means: raise ValueError('empty paired sample')
    rng = random.Random(SEED)
    boot = sorted(statistics.mean(rng.choices(means, k=len(means))) for _ in range(2000))
    def interval(tail):
        return [boot[math.floor(tail*1999)], boot[math.ceil((1-tail)*1999)]]
    return {'score': statistics.mean(means), 'ci95': interval(.025),
            'ci98_75_bonferroni_four': interval(.00625)}


def trace_queries(directory, names):
    pending, position, queries, options = {}, {}, defaultdict(list), defaultdict(dict)
    with gzip.open(directory/'engine.log.gz', 'rt', encoding='utf-8') as stream:
        for line in stream:
            if not line.startswith('[Engine]'): continue
            match = re.search(r'>\s+(\S+) (<---|--->) (.*)$', line.rstrip('\r\n'))
            if not match: raise ValueError('unparsed engine trace')
            name, arrow, command = match.groups()
            if name not in names: raise ValueError('unknown trace engine')
            if arrow=='<---':
                if command.startswith('position '): position[name] = hashlib.sha256(command.encode()).hexdigest()
                elif command.startswith('setoption name '):
                    key, value = command[len('setoption name '):].split(' value ', 1)
                    options[name][key] = value
                elif command.startswith('go '):
                    if name in pending: raise ValueError('overlapping queries')
                    pending[name] = {'position_sha256': position[name], 'go': command, 'pv': []}
            elif command.startswith('info depth '):
                if name not in pending: raise ValueError('info outside query')
                if ' pv ' in command: pending[name]['pv'] = command.split(' pv ',1)[1].split()
            elif command.startswith('info string ucl_stats '):
                if name not in pending or 'stats' in pending[name]: raise ValueError('unmatched final stats')
                pending[name]['stats'] = json.loads(command.split('ucl_stats ',1)[1])
            elif command.startswith('bestmove '):
                q = pending.pop(name)
                if 'stats' not in q: raise ValueError('bestmove without final stats')
                q['move'] = command.split()[1]; queries[name].append(q)
            elif 'command rejected' in command or 'search error' in command:
                raise ValueError('engine trace rejection: '+command)
    if pending: raise ValueError('unfinished telemetry query')
    return queries, options


def analyze_group(group, directory, output):
    directory = Path(directory)
    record = validate_bundle(directory/'record.json', json.loads((ROOT/'schemas/experiment-v1.schema.json').read_text()))
    names = [e['name'] for e in record['engines']]
    queries, actual_options = trace_queries(directory, names)
    for e in record['engines']:
        for key, value in e['options'].items():
            actual = actual_options[e['name']].get(key)
            expected = str(value).lower() if isinstance(value,bool) else str(value)
            if key=='ModelFile':
                if actual is None or Path(actual.replace('\\','/')).name!='model-'+MODEL_SHA+'.txt':
                    raise ValueError('runtime model path mismatch')
            elif actual!=expected: raise ValueError('runtime option mismatch: '+key)
    openings = (directory/'openings.epd').read_text().splitlines()
    counters, means, terminations, moves, undershoots = Counter(), [], Counter(), [], []
    with (directory/'games.pgn').open(encoding='utf-8') as stream:
        game_index = 0
        while (game:=chess.pgn.read_game(stream, Visitor=CheckedGameBuilder)) is not None:
            round_index = game_index//2
            expected = chess.Board.from_epd(openings[round_index])[0]
            board = game.board()
            if board.fen()!=expected.fen() or game.headers['Round']!=str(round_index+1):
                raise ValueError('opening schedule mismatch')
            if game.headers['White']!=names[game_index%2]: raise ValueError('color schedule mismatch')
            final = check_game_result(game, require_natural=True)
            termination = game.headers['Termination']
            if termination=='adjudication':
                if len(list(game.mainline_moves()))!=300 or game.headers['Result']!='1/2-1/2':
                    raise ValueError('unexpected adjudication')
                terminations['MAXMOVES_150']+=1
            elif termination=='normal': terminations[final.outcome(claim_draw=True).termination.name]+=1
            else: raise ValueError('abnormal completed game')
            result = game.headers['Result']
            score = .5 if result=='1/2-1/2' else float((result=='1-0')==(game.headers['White']==names[0]))
            if game_index%2==0: means.append(score/2)
            else: means[-1]+=score/2
            root, history = 'position fen '+game.headers['FEN'], []
            for ply,node in enumerate(game.mainline(),1):
                name = game.headers['White' if board.turn else 'Black']
                index = counters[name]; counters[name]+=1
                q = queries[name][index]
                command = root+(' moves '+' '.join(history) if history else '')
                if q['position_sha256']!=hashlib.sha256(command.encode()).hexdigest() or q['move']!=node.move.uci():
                    raise ValueError('PGN/telemetry position or move mismatch')
                pv_board = board.copy()
                for move in q['pv']: pv_board.push_uci(move)
                if q['pv'] and q['pv'][0]!=q['move']: raise ValueError('PV mismatch')
                stats = q['stats']
                if group=='B':
                    parts=q['go'].split(); values=dict(zip(parts[1::2],parts[2::2]))
                    if values.get('nodes')!='50000' or stats['nodes']>50000:
                        raise ValueError('fixed-node command/counter mismatch')
                    remaining=int(values['wtime' if board.turn else 'btime'])
                    increment=int(values['winc' if board.turn else 'binc'])
                    allocation=max(0,min(remaining-10,remaining//30+increment//2-10))
                    if stats['elapsed_us']>=allocation*1000: raise ValueError('node search reached clock guard')
                    if stats['nodes']<50000:
                        reason = 'mate_proven' if abs(stats['score_cp'])>=30000-stats['depth'] and stats['depth']>0 else (
                            'root_draw' if board.outcome(claim_draw=True) else 'max_depth' if stats['depth']==128 else None)
                        if reason is None: raise ValueError('unclassified node undershoot; preserve for investigation')
                        undershoots.append({'game':game_index+1,'ply':ply,'engine':name,'reason':reason,**stats})
                moves.append({'game':game_index+1,'opening':round_index+1,'ply':ply,'engine':name,**q})
                history.append(node.move.uci()); board.push(node.move)
            game_index+=1
    if game_index!=400 or len(means)!=200 or any(len(queries[n])!=counters[n] for n in names):
        raise ValueError('incomplete schedule or orphan telemetry')
    boot = bootstrap(means)
    output=Path(output); output.mkdir(parents=True, exist_ok=True)
    (output/'moves.jsonl.gz').write_bytes(gzip.compress(''.join(json.dumps(r,sort_keys=True)+'\n' for r in moves).encode(),mtime=0))
    telemetry = analyze_r4(directory/'record.json')
    result = {'group':group,'record_sha256':sha256(directory/'record.json'),'statistics':record['results'],
        'paired_means':means,'bootstrap':boot,'elo_equivalent':elo_equivalent(boot['score']),
        'elo_ci95':[elo_equivalent(v) for v in boot['ci95']],
        'elo_ci98_75':[elo_equivalent(v) for v in boot['ci98_75_bonferroni_four']],
        'confirmatory_vs_half': 'above' if boot['ci98_75_bonferroni_four'][0]>.5 else 'below' if boot['ci98_75_bonferroni_four'][1]<.5 else 'inconclusive',
        'terminations':dict(terminations),'abnormal_games':0,'node_undershoots':undershoots,
        'runtime_options':dict(actual_options),'telemetry':telemetry,
        'moves_sha256':sha256(output/'moves.jsonl.gz')}
    if boot['ci95']!=record['results']['score_ci95_paired_bootstrap']: raise ValueError('bootstrap implementation disagreement')
    write_json(output/'analysis.json',result)
    return result


def run(directory, output):
    directory, output = Path(directory), Path(output)
    if directory.resolve() == output.resolve():
        raise ValueError('write analysis separately from source bundles')
    result = {'code': git_state(ROOT), 'groups': {}}
    for group in 'ABCD':
        result['groups'][group] = analyze_group(group, directory/group, output/group)
    result['exploratory_paired_contrasts'] = {
        label: bootstrap([x-y for x,y in zip(result['groups'][a]['paired_means'],
                         result['groups'][b]['paired_means'], strict=True)])
        for label,a,b in [('C-A','C','A'), ('B-A','B','A')]}
    write_json(output/'summary.json', result)
    return result


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input', required=True)
    p.add_argument('--output', required=True)
    a = p.parse_args()
    print(json.dumps(run(a.input, a.output), indent=2))

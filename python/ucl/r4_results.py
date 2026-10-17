"""R4 match telemetry analysis; existing PGN integrity and paired statistics remain authoritative."""
from collections import Counter,defaultdict
import gzip
import json
from pathlib import Path
import re
import statistics

import chess.pgn

from .integrity import validate_bundle
from .records import sha256,write_json
from .report import CheckedGameBuilder,check_game_result,elo_equivalent
from .r4_training import ROOT


def analyze(record_path, completed_prefix_games=None):
    path=Path(record_path)
    record=validate_bundle(path,json.loads((ROOT/'schemas/experiment-v1.schema.json').read_text()),completed_prefix_games)
    names=[e['name'] for e in record['engines']]
    traces=defaultdict(list)
    with gzip.open(path.parent/'engine.log.gz','rt',encoding='utf-8') as stream:
        for line in stream:
            marker=' ---> info string ucl_stats '
            if marker not in line:continue
            prefix,text=line.split(marker,1);name=prefix.split()[-1]
            if name not in names:raise ValueError('unrecognized telemetry engine')
            stats=json.loads(text)
            for key in ('nodes','qnodes','depth','elapsed_us'):
                if type(stats[key]) is not int or stats[key]<0:raise ValueError('invalid final search counter')
            if stats['qnodes']>stats['nodes']:raise ValueError('invalid final qnodes')
            traces[name].append(stats)
    moves=Counter();pgn_nodes=Counter();coverage=Counter();wall=Counter();natural=Counter();endings=Counter()
    with (path.parent/'games.pgn').open() as stream:
        while (game:=chess.pgn.read_game(stream,Visitor=CheckedGameBuilder)) is not None:
            final=check_game_result(game,require_natural=True)
            ending=game.headers.get('Termination','unknown');endings[ending]+=1
            if ending=='normal':natural[final.outcome(claim_draw=True).termination.name]+=1
            board=game.board()
            for node in game.mainline():
                name=game.headers['White' if board.turn else 'Black'];moves[name]+=1
                match=re.search(r'(?:^|[ ,])n=(\d+)(?:[, ]|$)',node.comment)
                if match:pgn_nodes[name]+=int(match[1]);coverage[name]+=1
                seconds=re.search(r'(?:^| )([0-9]+\.[0-9]+)s(?:[, ]|$)',node.comment)
                if seconds:wall[name]+=float(seconds[1])
                if node.move not in board.legal_moves:raise ValueError('unvalidated PGN move')
                board.push(node.move)
    summaries={}
    for name in names:
        orphan_queries=max(0,len(traces[name])-moves[name])
        if completed_prefix_games is not None:
            traces[name]=traces[name][:moves[name]]
        if len(traces[name])!=moves[name] or coverage[name]!=moves[name]:
            raise ValueError('telemetry/PGN move coverage mismatch: '+name)
        total_nodes=sum(r['nodes'] for r in traces[name]);us=sum(r['elapsed_us'] for r in traces[name])
        summaries[name]={'moves':moves[name],'orphan_queries_from_incomplete_game':orphan_queries,'final_nodes':total_nodes,'final_qnodes':sum(r['qnodes'] for r in traces[name]),
            'engine_elapsed_us':us,'aggregate_final_nps':total_nodes*1e6/max(1,us),
            'completed_depth_median':statistics.median(r['depth'] for r in traces[name]),
            'completed_depth_counts':dict(Counter(str(r['depth']) for r in traces[name])),
            'pgn_last_completed_nodes':pgn_nodes[name],'pgn_move_wall_seconds_rounded_ms':wall[name],
            'counter_scope':'final includes interrupted iteration; PGN n= uses last completed UCI info'}
    r=record['tools']['completed_prefix']['results'] if completed_prefix_games is not None else record['results']
    ci=r['score_ci95_paired_bootstrap']
    result={'kind':'r4-match-analysis','record_sha256':sha256(path),'source_status':record['status'],
        'completed_prefix_games':completed_prefix_games,'source_error':record['error'],'games':r['games'],'paired_rounds':r['paired_rounds'],
        'wins':r['wins'],'draws':r['draws'],'losses':r['losses'],'score':r['score'],
        'score_ci95_paired_bootstrap':ci,'elo_equivalent':elo_equivalent(r['score']),
        'elo_equivalent_ci95':[elo_equivalent(p) for p in ci] if ci else None,
        'paired_score_counts':r['paired_score_counts'],'terminations':dict(endings),'natural_reasons':dict(natural),
        'abnormal_games':sum(n for name,n in endings.items() if name not in ('normal','adjudication')),
        'engines':summaries,'limitations':[f"Fixed {r['paired_rounds']} paired-opening sample and short clock; not SPRT or universal Elo.",
        'Opening dependence and desktop background activity limit external validity.',
        'Elo interval is monotone transform of descriptive paired-score percentile bootstrap.']}
    return result


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('record');p.add_argument('--output',required=True)
    p.add_argument('--completed-prefix-games',type=int)
    a=p.parse_args();result=analyze(a.record,a.completed_prefix_games);write_json(a.output,result);print(json.dumps(result,indent=2))

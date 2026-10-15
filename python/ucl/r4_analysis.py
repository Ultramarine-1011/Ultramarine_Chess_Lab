"""Single held-out R4 evaluation with game-cluster resampling and frozen provenance."""
from collections import defaultdict
import json
from pathlib import Path

import numpy as np
import chess

from .dataset import SEED
from .records import sha256, write_json, git_state
from .r4_training import ROOT, arrays, read_rows, metrics, loss_values
from .model import load_model


def game_means(values, rows):
    grouped=defaultdict(list)
    for value,row in zip(values,rows,strict=True): grouped[row['game_id']].append(float(value))
    return np.asarray([np.mean(grouped[g]) for g in sorted(grouped)])


def paired_interval(delta,rows,indices):
    means=game_means(delta,rows)
    boot=means[indices].mean(axis=1)
    return {'difference':float(means.mean()),'ci95':np.quantile(boot,[.025,.975]).tolist(),
            'ci99':np.quantile(boot,[.005,.995]).tolist(),
            'position_weighted_difference':float(np.mean(delta))}


def evaluate(study, freeze_path):
    study,freeze_path=Path(study),Path(freeze_path)
    freeze=json.loads(freeze_path.read_text())
    if sha256(study/'selection.json')!=freeze['selection_sha256']: raise ValueError('study selection changed after freeze')
    selection=json.loads((study/'selection.json').read_text())
    for name,m in selection['models'].items():
        if sha256(study/m['model_file'])!=freeze['models'][name]: raise ValueError('model changed after freeze')
        actual=load_model(study/m['model_file'],m['model_sha256'])
        expected=m['weights'][:len(actual)]
        if actual!=expected: raise ValueError('deployment weights do not match frozen study')
    rows,_=read_rows(selection['dataset'],selection['features'])
    selected,x,y,q=arrays(rows,'test')
    gids=sorted({r['game_id'] for r in selected})
    rng=np.random.default_rng(SEED)
    indices=rng.integers(0,len(gids),size=(2000,len(gids)))
    if (study/'test-results.json').exists():
        raise FileExistsError('held-out results already exist; use validation for development')
    losses={n:loss_values(x,y,m['weights']) for n,m in selection['models'].items()}
    result={'kind':'r4-independent-test','code':git_state(ROOT),'freeze_sha256':sha256(freeze_path),
        'games':len(gids),'positions':len(selected),'primary':'equal-game BCE',
        'models':{n:metrics(x,y,q,m['weights']) for n,m in selection['models'].items()},'contrasts':{}}
    # Five prespecified feature/candidate contrasts get Bonferroni 99% marginal
    # intervals, providing familywise >=95% nominal coverage for these five only.
    pairs=[('refit8','calibration'),('pawn','refit8'),('king','refit8'),('full','pawn'),('full','king')]
    others=[('frozen_r3','handcrafted'),('calibration','handcrafted'),('refit8','handcrafted'),
            (freeze['candidate'],'calibration'),(freeze['candidate'],'handcrafted')]
    for a,b in dict.fromkeys(pairs+others):
        result['contrasts'][a+' - '+b]={k:paired_interval(losses[a][k]-losses[b][k],selected,indices) for k in ('bce','brier')}
    result['bootstrap']={'unit':'whole game, all positions together; equal weight per game','resamples':2000,'seed':SEED,
        'simultaneous_family':[' - '.join(p) for p in pairs],
        'interpretation':'Game-conditional descriptive intervals; repeated players and only two future windows limit population inference.'}
    games=json.loads((Path(selection['dataset'])/'splits.json').read_text())
    strata={'white_to_move':lambda r:r['fen'].split()[1]=='w','black_to_move':lambda r:r['fen'].split()[1]=='b',
            'early_ply16_40':lambda r:r['ply']<=40,'later_ply41_160':lambda r:r['ply']>40,
            'draw_label':lambda r:r['label']==.5,'decisive_label':lambda r:r['label']!=.5}
    for month in sorted({games[r['game_id']]['month'] for r in selected}):
        strata['source_'+month]=lambda r,m=month:games[r['game_id']]['month']==m
    def phase(r):
        b=chess.Board(r['fen'])
        return sum(len(b.pieces(pt,c))*v for c in chess.COLORS for pt,v in
                   ((chess.KNIGHT,1),(chess.BISHOP,1),(chess.ROOK,2),(chess.QUEEN,4)))
    phases={r['position_id']:phase(r) for r in selected}
    strata.update(endgame_0_8=lambda r:phases[r['position_id']]<=8,
                  middle_9_16=lambda r:8<phases[r['position_id']]<=16,
                  opening_17_24=lambda r:phases[r['position_id']]>16)
    result['strata']={}
    for name,predicate in strata.items():
        group=[r for r in selected if predicate(r)]
        if group:
            _,sx,sy,sq=arrays(group,'test')
            result['strata'][name]={'games':len({r['game_id'] for r in group}),
                'models':{n:metrics(sx,sy,sq,m['weights']) for n,m in selection['models'].items()}}
    write_json(study/'test-results.json',result)
    return result


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--study',required=True);p.add_argument('--freeze',required=True)
    a=p.parse_args();print(json.dumps(evaluate(a.study,a.freeze),indent=2))

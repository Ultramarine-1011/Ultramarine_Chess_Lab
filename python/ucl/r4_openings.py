"""Frozen independent 2017-08 openings; selection uses identities, never model scores."""
import argparse
import gzip
import json
from pathlib import Path

import chess

from .dataset import SEED, digest, position_key, prepare, write_gzip
from .r4_data import bounded_source
from .records import git_state, sha256, write_json


def select(text,count,excluded,training_games=()):
    _,games,counts=prepare(text,metadata=True,opening_plies=12)
    seen=set(excluded);selected=[]
    for gid in sorted(games,key=lambda g:digest(f'{SEED}:{g}')):
        if gid in training_games or 'opening_fen' not in games[gid]:continue
        b=chess.Board(games[gid]['opening_fen']);key=position_key(b)
        if key in seen:continue
        seen.add(key)
        selected.append({'id':f'r4-{len(selected)+1:03}','game_id':gid,'site':games[gid]['site'],
            'utc':games[gid]['utc'],'eco':games[gid]['eco'],'fen':b.fen(),
            'moves':games[gid]['opening_moves'],'position_id':key})
        if len(selected)==count:break
    return selected,counts


def acquire(output,cache='.tools/r4-sources',count=200):
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    text,source=bounded_source('2017-08',cache)
    old=json.loads(Path('experiments/openings/r3-v1.json').read_text())
    excluded={position_key(chess.Board(p['fen'])) for p in old['positions']}
    training=json.loads(Path('experiments/results/r4-data-v1/splits.json').read_text())
    positions,counts=select(text,count,excluded,training)
    write_gzip(output/'source.pgn.gz',text)
    write_json(output/'positions.json',positions)
    (output/'openings.epd').write_text(''.join(chess.Board(p['fen']).epd(id=p['id'])+'\n' for p in positions),encoding='utf-8',newline='\n')
    manifest={'kind':'r4-independent-openings','source':source,'seed':SEED,'code':git_state(Path.cwd()),
        'selection':'first unique 12-ply positions in SHA256(seed:game_id) order; exclude R3 positions and R4 games',
        'target':count,'positions':len(positions),'status':'PASS' if len(positions)==count else 'PARTIAL',
        'filter_counts':counts,'r3_openings_sha256':sha256('experiments/openings/r3-v1.json'),
        'r4_splits_sha256':sha256('experiments/results/r4-data-v1/splits.json'),
        'files':{p.name:{'sha256':sha256(p),'bytes':p.stat().st_size} for p in sorted(output.iterdir())}}
    write_json(output/'manifest.json',manifest)
    return manifest


def validate(directory):
    directory=Path(directory);m=json.loads((directory/'manifest.json').read_text())
    for name,meta in m['files'].items():
        p=directory/name
        if Path(name).name!=name or sha256(p)!=meta['sha256'] or p.stat().st_size!=meta['bytes']:
            raise ValueError('opening artifact integrity mismatch')
    old=json.loads(Path('experiments/openings/r3-v1.json').read_text())
    training=json.loads(Path('experiments/results/r4-data-v1/splits.json').read_text())
    if sha256('experiments/openings/r3-v1.json')!=m['r3_openings_sha256'] or sha256('experiments/results/r4-data-v1/splits.json')!=m['r4_splits_sha256']:
        raise ValueError('opening exclusion identity mismatch')
    positions,counts=select(gzip.decompress((directory/'source.pgn.gz').read_bytes()).decode(),m['target'],
        {position_key(chess.Board(p['fen'])) for p in old['positions']},training)
    if positions!=json.loads((directory/'positions.json').read_text()) or counts!=m['filter_counts']:
        raise ValueError('opening source reconstruction mismatch')
    expected=''.join(chess.Board(p['fen']).epd(id=p['id'])+'\n' for p in positions)
    if expected!=(directory/'openings.epd').read_text():raise ValueError('opening EPD mismatch')
    return m


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('operation',choices=['acquire','validate'])
    p.add_argument('--output',required=True);a=p.parse_args()
    print(json.dumps(acquire(a.output) if a.operation=='acquire' else validate(a.output),indent=2))

"""Recover the fixed R4 sample without rerunning completed pairs or concealing failures."""
from collections import Counter
import copy
import hashlib
import io
import json
from pathlib import Path
import statistics
import tempfile
import subprocess

import chess
import chess.pgn

from .integrity import validate_bundle
from .r4_results import analyze,elo_equivalent
from .r4_training import ROOT
from .records import git_state,sha256,write_json
from .report import CheckedGameBuilder,summarize_pgn

ORIGINAL=Path('experiments/results/r4-match-final-20261015')
RECOVERY=Path('experiments/results/r4-recovery-v1')
CONTINUATION=Path('experiments/results/r4-match-continuation-20261015')
FINAL=Path('experiments/results/r4-study-final-20261015')


def prepare():
    schema=json.loads((ROOT/'schemas/experiment-v1.schema.json').read_text())
    record=validate_bundle(ORIGINAL/'record.json',schema,completed_prefix_games=120)
    warning='Warning; No info line available to extract score from engine Handcrafted'
    if warning not in (ORIGINAL/'fastchess.log').read_text():raise ValueError('unexpected recovery reason')
    config=json.loads((ROOT/'experiments/configs/r4-match.json').read_text())
    if record['parameters']!=config:raise ValueError('original frozen configuration changed')
    lines=(ORIGINAL/'openings.epd').read_text().splitlines(keepends=True)
    if len(lines)!=200:raise ValueError('unexpected frozen opening count')
    RECOVERY.mkdir(parents=True,exist_ok=False)
    (RECOVERY/'openings.epd').write_bytes(''.join(lines[60:]).encode())
    continuation=copy.deepcopy(config);continuation['rounds']=140
    continuation['openings']['path']=str(RECOVERY/'openings.epd')
    write_json(ROOT/'experiments/configs/r4-match-continuation.json',continuation)
    patch=subprocess.check_output(['git','diff',record['code']['revision'],'--','engine/src/uci.cpp'],text=True)
    (RECOVERY/'uci-info.patch').write_text(patch)
    plan={'kind':'r4-fixed-sample-recovery','status':'frozen-before-continuation','code':git_state(ROOT),
        'original_record':str(ORIGINAL/'record.json'),'original_record_sha256':sha256(ORIGINAL/'record.json'),
        'original_config_sha256':sha256(ROOT/'experiments/configs/r4-match.json'),
        'candidate_freeze_sha256':sha256(ROOT/'experiments/results/r4-models-v1/freeze.json'),
        'prefix_games':120,'prefix_pairs':60,'remaining_games':280,'remaining_pairs':140,'total_pairs':200,
        'reason':warning,'decision':'Keep all first120 games. Rerun only unfinished game121 as part of original remaining140 pairs; no model, clock, opening, total-sample or statistical change.',
        'approved_uci_sha256':sha256(ROOT/'engine/src/uci.cpp'),
        'remaining_openings_sha256':sha256(RECOVERY/'openings.epd'),
        'continuation_config_sha256':sha256(ROOT/'experiments/configs/r4-match-continuation.json'),
        'uci_patch_sha256':sha256(RECOVERY/'uci-info.patch')}
    write_json(RECOVERY/'plan.json',plan)
    return plan


def engine_code_controls(before,after,approved_uci_sha):
    files=lambda rev:subprocess.check_output(['git','ls-tree','-r','--name-only',rev,'engine'],text=True).splitlines()
    a,b=files(before),files(after)
    if a!=b:raise ValueError('engine source inventory changed during recovery')
    evidence={}
    for name in a:
        left=subprocess.check_output(['git','show',f'{before}:{name}'])
        right=subprocess.check_output(['git','show',f'{after}:{name}'])
        lh,rh=hashlib.sha256(left).hexdigest(),hashlib.sha256(right).hexdigest()
        if name=='engine/src/uci.cpp':
            if rh!=approved_uci_sha:raise ValueError('UCI change differs from frozen repair')
        elif lh!=rh:raise ValueError('search/evaluation/source changed during recovery: '+name)
        evidence[name]={'before':lh,'after':rh}
    return evidence


def normalized_fen(fen):
    return ' '.join(chess.Board(fen).fen().split()[:4])


def combine(sources,opening_lines,output):
    expected=[normalized_fen(chess.Board.from_epd(line)[0].fen()) for line in opening_lines]
    games=[]
    for path,offset,count in sources:
        local=[]
        with Path(path).open() as stream:
            while (game:=chess.pgn.read_game(stream,Visitor=CheckedGameBuilder)) is not None:local.append(game)
        if len(local)!=count:raise ValueError('study source game count mismatch')
        for i,game in enumerate(local):
            if game.headers['Round']!=str(i//2+1):raise ValueError('unexpected source pair ordering')
            round_number=offset+i//2+1
            if normalized_fen(game.board().fen())!=expected[round_number-1]:raise ValueError('study opening order mismatch')
            game.headers['Round']=str(round_number)
            games.append(game)
    if len(games)!=2*len(opening_lines):raise ValueError('incomplete fixed study')
    output=Path(output)
    output.write_text('\n\n'.join(g.accept(chess.pgn.StringExporter(headers=True,variations=False,comments=True)) for g in games)+'\n',encoding='utf-8',newline='\n')


def finalize(output=FINAL):
    output=Path(output)
    plan=json.loads((RECOVERY/'plan.json').read_text());schema=json.loads((ROOT/'schemas/experiment-v1.schema.json').read_text())
    for path,key in ((ORIGINAL/'record.json','original_record_sha256'),
        (ROOT/'experiments/configs/r4-match.json','original_config_sha256'),
        (ROOT/'experiments/results/r4-models-v1/freeze.json','candidate_freeze_sha256'),
        (RECOVERY/'openings.epd','remaining_openings_sha256'),
        (ROOT/'experiments/configs/r4-match-continuation.json','continuation_config_sha256'),
        (RECOVERY/'uci-info.patch','uci_patch_sha256')):
        if sha256(path)!=plan[key]:raise ValueError('recovery plan artifact changed: '+str(path))
    a=validate_bundle(ORIGINAL/'record.json',schema,completed_prefix_games=plan['prefix_games'])
    b=validate_bundle(CONTINUATION/'record.json',schema)
    if b['parameters']!=json.loads((ROOT/'experiments/configs/r4-match-continuation.json').read_text()):raise ValueError('continuation configuration mismatch')
    if a['code']['dirty'] or b['code']['dirty']:raise ValueError('formal study requires clean binaries')
    for ea,eb in zip(a['engines'],b['engines'],strict=True):
        if ea['name']!=eb['name'] or ea['options']!=eb['options']:raise ValueError('engine/model options changed')
        for key in ('compiler','build_type','flags'):
            if ea['build_info'][key]!=eb['build_info'][key]:raise ValueError('compiler controls changed')
    controls=engine_code_controls(a['code']['revision'],b['code']['revision'],plan['approved_uci_sha256'])
    original_lines=(ORIGINAL/'openings.epd').read_text().splitlines()
    if (CONTINUATION/'openings.epd').read_text().splitlines()!=original_lines[plan['prefix_pairs']:]:raise ValueError('continuation is not exact unused opening suffix')
    if len(set(normalized_fen(chess.Board.from_epd(line)[0].fen()) for line in original_lines))!=200:raise ValueError('study openings not unique')
    output.mkdir(parents=True,exist_ok=False)
    combine([(ORIGINAL/'games.pgn',0,120),(CONTINUATION/'games.pgn',60,280)],original_lines,output/'combined-games.pgn')
    statistics_=summarize_pgn(output/'combined-games.pgn',a['engines'][0]['name'],a['engines'][1]['name'],400,a['seed'])
    if statistics_['paired_rounds']!=200:raise ValueError('fixed200 pairs not recovered')
    analyses=[analyze(ORIGINAL/'record.json',120),analyze(CONTINUATION/'record.json')]
    for i,item in enumerate(analyses):write_json(output/f'batch-{i+1}-analysis.json',item)
    telemetry={}
    for name in (e['name'] for e in a['engines']):
        groups=[item['engines'][name] for item in analyses]
        sums={key:sum(g[key] for g in groups) for key in ('moves','final_nodes','final_qnodes','engine_elapsed_us','pgn_last_completed_nodes','pgn_move_wall_seconds_rounded_ms','orphan_queries_from_incomplete_game')}
        hist=Counter()
        for group in groups:hist.update(group['completed_depth_counts'])
        depths=[int(depth) for depth,n in hist.items() for _ in range(n)]
        telemetry[name]={**sums,'aggregate_final_nps':sums['final_nodes']*1e6/max(1,sums['engine_elapsed_us']),
            'completed_depth_counts':dict(hist),'completed_depth_median':statistics.median(depths)}
    ci=statistics_['score_ci95_paired_bootstrap']
    result={'kind':'r4-fixed-study','status':'completed','code':git_state(ROOT),
        'plan_sha256':sha256(RECOVERY/'plan.json'),'results':statistics_,
        'elo_equivalent':elo_equivalent(statistics_['score']),'elo_equivalent_ci95':[elo_equivalent(v) for v in ci],
        'batches':[{'record':str(p/'record.json'),'sha256':sha256(p/'record.json'),'source_status':status,'games':n,'opening_range':opening}
                   for p,status,n,opening in ((ORIGINAL,'failed',120,[1,60]),(CONTINUATION,'completed',280,[61,200]))],
        'telemetry':telemetry,'engine_code_controls':controls,
        'deviation':'Strict-mode protocol warning interrupted the original run after60 complete pairs. Preserve its failed status and all120 results; only UCI depth0 info output changed for remaining140 pairs. Search/evaluation/model/clock/opening/sample unchanged. Incomplete game121 abandoned and repeated within the original remaining sample.',
        'natural_reasons':dict(sum((Counter(x['natural_reasons']) for x in analyses),Counter())),
        'abnormal_completed_games':sum(x['abnormal_games'] for x in analyses),
        'files':{p.name:{'sha256':sha256(p),'bytes':p.stat().st_size} for p in sorted(output.iterdir())}}
    write_json(output/'record.json',result)
    return result


def validate(directory=FINAL):
    directory=Path(directory);stored=json.loads((directory/'record.json').read_text())
    if stored['kind']!='r4-fixed-study' or stored['status']!='completed':raise ValueError('study not complete')
    for name,meta in stored['files'].items():
        p=directory/name
        if Path(name).name!=name or sha256(p)!=meta['sha256'] or p.stat().st_size!=meta['bytes']:
            raise ValueError('derived study artifact changed')
    with tempfile.TemporaryDirectory() as tmp:
        rebuilt=finalize(Path(tmp)/'reconstructed')
    for key in stored:
        if key!='code' and stored[key]!=rebuilt[key]:raise ValueError('study reconstruction mismatch: '+key)
    return stored


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('operation',choices=['prepare','finalize','validate']);a=p.parse_args()
    print(json.dumps(prepare() if a.operation=='prepare' else validate() if a.operation=='validate' else finalize(),indent=2))

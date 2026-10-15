"""Continue only predeclared missing whole R5 groups B/C/D in a clean checkout."""
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[3] if 'docs' in str(Path(__file__)) else Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'python'))
from ucl.r5_study import RESULTS, CONFIGS, EVIDENCE
from ucl.r5_performance import host
from ucl.match import run_match
from ucl.integrity import validate_bundle
from ucl.records import git_state, sha256, utc_now, write_json


def run():
    state=git_state(ROOT)
    if state['dirty']: raise ValueError('continuation requires a clean frozen checkout')
    plan=json.loads((EVIDENCE/'recovery-plan.json').read_text(encoding='utf-8'))
    if plan['remaining_groups']!=list('BCD'): raise ValueError('unexpected continuation schedule')
    if sha256(Path(__file__))!=plan['continuation_script_sha256']: raise ValueError('continuation script changed')
    frozen=json.loads((EVIDENCE/'formal-freeze.json').read_text(encoding='utf-8'))
    if sha256(ROOT/'python/ucl/r5_study.py')!=frozen['analysis_sha256']: raise ValueError('frozen runner source changed')
    for n,h in plan['frozen_source_files'].items():
        if sha256(ROOT/n)!=h: raise ValueError('source changed: '+n)
    for n in 'BCD':
        if (RESULTS/f'r5-match-{n.lower()}-v1').exists(): raise ValueError('output already exists: '+n)
    if sha256(RESULTS/'r5-match-a-v1/record.json')!=plan['completed_A_record_sha256']:
        raise ValueError('completed A changed')
    if sha256(ROOT/'.tools/bin/fastchess.exe')!=frozen['tool_sha256']: raise ValueError('tool changed')
    if sha256(RESULTS/'r5-openings-v1/openings.epd')!=frozen['openings_sha256']: raise ValueError('openings changed')
    schema=json.loads((ROOT/'schemas/experiment-v1.schema.json').read_text())
    validate_bundle(RESULTS/'r5-match-a-v1/record.json',schema)
    output=RESULTS/'r5-match-conditions-continuation-v1';output.mkdir(parents=True,exist_ok=False)
    index={'kind':'r5-whole-group-continuation','code':state,'started_at':utc_now(),'status':'running','groups':{},'error':None,
           'plan_sha256':sha256(EVIDENCE/'recovery-plan.json')}
    write_json(output/'index.json',index)
    try:
        for group in 'BCD':
            if git_state(ROOT)['dirty']: raise ValueError('source became dirty before '+group)
            if sha256(CONFIGS/f'{group}.json')!=frozen['configs'][group]: raise ValueError('config changed')
            if shutil.disk_usage(ROOT).free<10*1024**3: raise ValueError('disk guard failed')
            host(output/f'{group}-before.json')
            target=RESULTS/f'r5-match-{group.lower()}-v1'
            record=run_match(ROOT,CONFIGS/f'{group}.json',target,'.tools/bin/fastchess.exe')
            index['groups'][group]={'status':record['status'],'record_sha256':sha256(target/'record.json')}
            write_json(output/'index.json',index)
            host(output/f'{group}-after.json')
            if record['status']!='completed': raise ValueError(record['error'])
            validate_bundle(target/'record.json',schema)
        index['status']='PASS'
    except Exception as exc:
        index.update(status='FAIL',error=f'{type(exc).__name__}: {exc}')
    index['finished_at']=utc_now();write_json(output/'index.json',index)
    return index


if __name__=='__main__':
    r=run();print(json.dumps(r,indent=2));raise SystemExit(r['status']!='PASS')

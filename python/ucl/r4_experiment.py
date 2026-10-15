"""Prepare controls and freeze one R4 candidate using development metrics and measured cost."""
import argparse
import json
from pathlib import Path

from .records import sha256,write_json,git_state
from .r4_training import ROOT
from .integrity import validate_bundle

GROUPS=('refit8','pawn','king','full')


def engines(study,name):
    study=Path(study);selection=json.loads((study/'selection.json').read_text());model=selection['models'][name]
    common={'path':'build/release/ucl','revision':'HEAD','build':'CMake Release; same binary; one search thread',
            'ucl_build_info':True}
    options={'Quiescence':True,'UseTT':True,'PVOrdering':True,'Hash':16,'MoveOverhead':10}
    return [{**common,'name':name,'options':{**options,'ModelSHA256':model['model_sha256'],
        'ModelFile':str(study/model['model_file']),'Evaluator':'Linear'}},
        {**common,'name':'Handcrafted','options':{**options,'Evaluator':'Handcrafted'}}]


def prepare(study,configs):
    configs=Path(configs);configs.mkdir(parents=True,exist_ok=False)
    for name in GROUPS:
        config={'version':1,'seed':20261015,'suite':'experiments/positions/r2-v1.json','repeats':3,
                'limits':[{'depth':3},{'depth':4}],'engines':engines(study,name),'static_evaluation':True}
        write_json(configs/(name+'-benchmark.json'),config)


def choose(models,costs):
    eligible=[n for n in GROUPS if models[n]['success'] and costs[n]<=10]
    if not eligible:raise ValueError('no candidate satisfies frozen cost/convergence gate')
    return min(eligible,key=lambda n:(models[n]['validation']['equal_game']['bce'],len(models[n]['active'])))


def freeze(study,benchmarks,match_config):
    study,benchmarks=Path(study),Path(benchmarks)
    if (study/'freeze.json').exists() or Path(match_config).exists():raise ValueError('refuse to replace candidate freeze/config')
    selection=json.loads((study/'selection.json').read_text());costs={};evidence={}
    schema=json.loads((ROOT/'schemas/benchmark-v1.schema.json').read_text())
    for name in GROUPS:
        path=benchmarks/name/'record.json'
        record=validate_bundle(path,schema)
        if record['status']!='completed' or record['code']['dirty']:raise ValueError('candidate cost needs clean complete benchmark')
        model=[e for e in record['engines'] if e['name']==name]
        if len(model)!=1 or model[0]['evaluation']['model_sha256']!=selection['models'][name]['model_sha256']:
            raise ValueError('benchmark/model identity mismatch')
        s=record['tools']['static_evaluation']['summary']
        costs[name]=s['mean_position_median_linear_ns']/s['mean_position_median_handcrafted_ns']
        evidence[name]={'path':str(path),'sha256':sha256(path),'cost_ratio':costs[name]}
    chosen=choose(selection['models'],costs)
    frozen={'kind':'r4-candidate-freeze','code':git_state(ROOT),'selection_sha256':sha256(study/'selection.json'),
        'candidate':chosen,'models':{n:m['model_sha256'] for n,m in selection['models'].items()},
        'cost_evidence':evidence,'rule':'minimum validation equal-game BCE; converged; ratio of mean per-position median static ns <=10; fewer active dimensions on exact tie',
        'analysis_sha256':sha256(ROOT/'python/ucl/r4_analysis.py'),
        'protocol_sha256':sha256(ROOT/'docs/r4/protocol.md'),
        'openings_manifest_sha256':sha256(ROOT/'experiments/results/r4-openings-v1/manifest.json'),
        'openings_epd_sha256':sha256(ROOT/'experiments/results/r4-openings-v1/openings.epd')}
    write_json(study/'freeze.json',frozen)
    config={'version':1,'comparison':'ablation','seed':20261015,'engines':engines(study,chosen),
        'rounds':200,'games':2,'concurrency':1,'pgn_telemetry':True,'tc':'1+0.01','maxmoves':150,'timeout_seconds':10800,
        'openings':{'path':'experiments/results/r4-openings-v1/openings.epd','format':'epd','order':'sequential'}}
    write_json(match_config,config)
    return frozen


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('operation',choices=['prepare','freeze'])
    p.add_argument('--study',default='experiments/results/r4-models-v1')
    p.add_argument('--configs',default='experiments/configs/r4')
    p.add_argument('--benchmarks',default='experiments/results/r4-benchmarks-v1')
    p.add_argument('--match-config',default='experiments/configs/r4-match.json');a=p.parse_args()
    if a.operation=='prepare':prepare(a.study,a.configs)
    else:print(json.dumps(freeze(a.study,a.benchmarks,a.match_config),indent=2))

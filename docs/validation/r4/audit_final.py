"""Final R4 requirement audit; use existing validators, never rerun test selection or matches."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from ucl.dataset import validate_dataset as validate_r3
from ucl.r4_data import validate_dataset as validate_r4
from ucl.r4_openings import validate as validate_openings
from ucl.r4_training import read_rows
from ucl.r4_study import validate as validate_study
from ucl.records import git_state,sha256,write_json
from ucl.training import TrainingSpec,read_features,validate_model_manifest
from ucl.model import load_model
from ucl.integrity import validate_bundle

ROOT=Path(__file__).resolve().parents[3]
# This file is saved at docs/validation/r4/audit_final.py before execution.
os.chdir(ROOT)
checks={'code':git_state(ROOT),'worktree_changes':subprocess.check_output(['git','status','--short'],cwd=ROOT,text=True).splitlines()}
checks['r3_datasets']={str(n):validate_r3(ROOT/f'experiments/results/r3-data-v{n}')['counts'] for n in (1,2)}
spec=TrainingSpec(str(ROOT/'experiments/results/r3-data-v2/manifest.json'),'handcrafted-v1',20261015,
    'white-game-result',str(ROOT/'experiments/results/r3-data-v2/splits.json'))
checks['r3_features']=len(read_features(ROOT/'experiments/results/r3-features-v2/manifest.json',spec)[0])
checks['r3_model']=validate_model_manifest(ROOT/'experiments/results/r3-model-v1/model-manifest.json')['model_sha256']
data=ROOT/'experiments/results/r4-data-v1';study=ROOT/'experiments/results/r4-models-v1'
checks['r4_dataset']=validate_r4(data)['targets'];assert all(checks['r4_dataset'].values())
checks['r4_openings']=validate_openings(ROOT/'experiments/results/r4-openings-v1')['positions'];assert checks['r4_openings']==200
rows,provenance=read_rows(data,ROOT/'experiments/results/r4-features-v2')
selection=json.loads((study/'selection.json').read_text());freeze=json.loads((study/'freeze.json').read_text())
assert sha256(study/'selection.json')==freeze['selection_sha256']
assert sha256(ROOT/'python/ucl/r4_analysis.py')==freeze['analysis_sha256']
assert sha256(ROOT/'docs/r4/protocol.md')==freeze['protocol_sha256']
checks['models']={}
for name,m in selection['models'].items():
    weights=load_model(study/m['model_file'],freeze['models'][name])
    assert weights==m['weights'][:len(weights)]
    if name!='frozen_r3':
        tokens=(study/m['model_file']).read_text().split();n=len(weights)
        assert tokens[12+n]==sha256(data/'manifest.json') and tokens[14+n]==sha256(data/'splits.json')
    checks['models'][name]={'sha256':m['model_sha256'],'dimensions':len(weights)}
assert checks['models']['frozen_r3']['sha256']==checks['r3_model']
marker=json.loads((study/'test-evaluation.started.json').read_text());test=json.loads((study/'test-results.json').read_text())
ids=[r['position_id'] for r in rows if r['split']=='test']
assert marker['test_position_ids_sha256']==hashlib.sha256('\n'.join(ids).encode()).hexdigest()
assert marker['freeze_sha256']==sha256(study/'freeze.json')==test['freeze_sha256']
assert test['games']==2173 and test['positions']==14570 and test['code']['dirty'] is False
checks['independent_test']={'model_count':len(test['models']),'test_sha256':sha256(study/'test-results.json'),'games':test['games'],'positions':test['positions'],'code':test['code']}
records=subprocess.check_output(['git','ls-files','experiments/results/*/record.json'],cwd=ROOT,text=True).splitlines()
records=sorted(set(records+['experiments/results/r4-match-continuation-20261015/record.json']))
checks['bundles']=[]
for name in records:
    if '/r4-study-final-' in name:continue
    path=ROOT/name;record=json.loads(path.read_text());schema_name='benchmark-v1.schema.json' if record['kind']=='benchmark' else 'experiment-v1.schema.json'
    schema=json.loads((ROOT/'schemas'/schema_name).read_text())
    if name=='experiments/results/r4-match-final-20261015/record.json':
        try:validate_bundle(path,schema)
        except ValueError as exc:assert 'failed' in str(exc)
        else:raise AssertionError('failed original run incorrectly accepted')
        checked=validate_bundle(path,schema,completed_prefix_games=120)
        status='FAILED_ORIGINAL_WITH_VALID120_GAME_PREFIX'
        assert checked['tools']['completed_prefix']['results']['paired_rounds']==60
    else:
        validate_bundle(path,schema);status='PASS'
    checks['bundles'].append({'path':name,'sha256':sha256(path),'status':status})
checks['study']=validate_study(ROOT/'experiments/results/r4-study-final-20261015')['results']
assert checks['study']['games']==400 and checks['study']['paired_rounds']==200
base='0d7a4f5'
old=subprocess.check_output(['git','ls-tree','-r','--name-only',base,'experiments/results','docs/r3'],cwd=ROOT,text=True).splitlines()
changed=[]
for name in old:
    if subprocess.check_output(['git','diff',base,'HEAD','--',name],cwd=ROOT):changed.append(name)
assert not changed
checks['r1_r3_existing_evidence_unchanged']=True
assert not subprocess.check_output(['git','diff',base,'HEAD','--','engine/src/search.cpp','engine/src/evaluator.cpp'],cwd=ROOT)
checks['search_and_handcrafted_source_unchanged']=True
assert not subprocess.check_output(['git','ls-files','build','.tools','.venv'],cwd=ROOT)
checks['no_builds_binaries_venv_tracked']=True
p=subprocess.run([str(ROOT/'build/release/ucl')],input='uci\nevalinfo\nquit\n',capture_output=True,text=True,check=True)
identity=[json.loads(s.removeprefix('info string ucl_evaluator ')) for s in p.stdout.splitlines() if s.startswith('info string ucl_evaluator ')]
assert identity==[{'evaluator':'handcrafted-v1','model_sha256':None}]
checks['default_evaluator']=identity[0]
checks['windows_physical_host']='NOT_RUN'
write_json(ROOT/'docs/validation/r4/final-audit.json',checks)
print('PASS: R3/R4 data, features/models, test freeze, all retained bundles, fixed400 games, unchanged history/default/search, no generated binaries tracked')

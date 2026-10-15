"""R4 equal-game calibration and regularized ablation study; no test access in fit."""
from collections import Counter
import gzip
import importlib.metadata
import json
from pathlib import Path
import time

import numpy as np
from scipy.optimize import minimize, minimize_scalar
from scipy.special import expit

from .dataset import SEED
from .feature_data import WEIGHTS
from .model import encode_model, load_model
from .records import git_state, hardware, sha256, write_json
from .training import objective, LAMBDAS, TAU, TrainingSpec

ROOT=Path(__file__).resolve().parents[2]


def read_rows(dataset, features):
    dataset,features=Path(dataset),Path(features)
    m=json.loads((features/'manifest.json').read_text())
    for path,key in ((dataset/'manifest.json','dataset_manifest_sha256'),(dataset/'splits.json','splits_sha256'),
                     (features/'features.jsonl.gz','features_sha256')):
        if sha256(path)!=m[key]: raise ValueError('R4 training input hash mismatch: '+key)
    rows=[json.loads(s) for s in gzip.decompress((features/'features.jsonl.gz').read_bytes()).decode().splitlines()]
    games=json.loads((dataset/'splits.json').read_text())
    if len(rows)!=m['count'] or len({r['position_id'] for r in rows})!=len(rows): raise ValueError('R4 feature count/duplicates')
    for r in rows:
        if r['split']!=games[r['game_id']]['split'] or r['label']!={'1-0':1.,'1/2-1/2':.5,'0-1':0.}[games[r['game_id']]['result']]:
            raise ValueError('R4 game/split/label mismatch')
        if len(r['features']) not in (8,14) or not np.isfinite(r['features']).all(): raise ValueError('R4 features invalid')
    return rows,m


def arrays(rows, split):
    selected=[r for r in rows if r['split']==split]
    if not selected: raise ValueError('empty split')
    x=np.asarray([r['features'] for r in selected],dtype=np.float64)
    y=np.asarray([r['label'] for r in selected],dtype=np.float64)
    counts=Counter(r['game_id'] for r in selected)
    q=np.asarray([1/counts[r['game_id']] for r in selected])
    return selected,x,y,q/q.sum()


def loss_values(x,y,w):
    z=x@np.asarray(w)/TAU
    return {'bce':np.logaddexp(0.,z)-y*z,'brier':(expit(z)-y)**2}


def metrics(x,y,q,w):
    losses=loss_values(x,y,w)
    return {'positions':len(y),'equal_game':{k:float(q@v) for k,v in losses.items()},
            'position_weighted':{k:float(np.mean(v)) for k,v in losses.items()}}


def optimize(x,y,q,indices,penalty):
    start=time.perf_counter()
    active=x[:,indices]
    rms=np.sqrt(q@(active*active));rms[rms==0]=1.
    baseline=np.zeros(x.shape[1]);baseline[:8]=WEIGHTS
    prior=baseline[indices]*rms/TAU
    fit=minimize(objective,prior,args=(active/rms,y,prior,penalty,q),jac=True,method='L-BFGS-B',
                 options={'maxiter':1000,'gtol':1e-9,'ftol':1e-12})
    w=np.zeros(x.shape[1]);w[indices]=fit.x*TAU/rms
    return {'weights':w.tolist(),'lambda':penalty,'rms':rms.tolist(),'active':indices,
        'success':bool(fit.success),'iterations':int(fit.nit),'objective':float(fit.fun),
        'gradient_inf':float(np.max(np.abs(fit.jac))),'message':str(fit.message),'seconds':time.perf_counter()-start}


def fit(dataset,features,output,expanded=False):
    rows,provenance=read_rows(dataset,features)
    _,x,y,q=arrays(rows,'train')
    _,vx,vy,vq=arrays(rows,'validation')
    if x.shape[1]!=(14 if expanded else 8): raise ValueError('study feature dimension mismatch')
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    baseline=np.zeros(x.shape[1]);baseline[:8]=WEIGHTS
    frozen=load_model(ROOT/'experiments/results/r3-model-v1/model.txt',
                      '446d18379cfa66e018c4be56218db044339e4be137309c9a17dfbab69874269b')
    old=np.zeros(x.shape[1]);old[:8]=frozen
    scalar=minimize_scalar(lambda s: metrics(x,y,q,baseline*s)['equal_game']['bce'],bounds=(.01,10),
                           method='bounded',options={'xatol':1e-12,'maxiter':1000})
    if not scalar.success: raise ValueError('positive scalar calibration failed')
    models={'handcrafted':{'weights':baseline.tolist()},'calibration':{'weights':(baseline*scalar.x).tolist(),
        'scale':float(scalar.x),'bounds':[.01,10],'success':bool(scalar.success)},'frozen_r3':{'weights':old.tolist()}}
    groups={'refit8':list(range(8))}
    if expanded: groups.update(pawn=list(range(11)),king=list(range(8))+[11,12,13],full=list(range(14)))
    for name,indices in groups.items():
        candidates=[]
        for penalty in LAMBDAS[1:]:
            c=optimize(x,y,q,indices,penalty)
            c['train']=metrics(x,y,q,c['weights']);c['validation']=metrics(vx,vy,vq,c['weights'])
            candidates.append(c)
        write_json(output/f'{name}-candidates.json',candidates)
        if not all(c['success'] for c in candidates): raise ValueError('optimizer failure; retained candidates')
        models[name]=min(candidates,key=lambda c:(c['validation']['equal_game']['bce'],-c['lambda']))
    for name,m in models.items():
        m['train']=metrics(x,y,q,m['weights']);m['validation']=metrics(vx,vy,vq,m['weights'])
        w=m['weights'] if expanded and name in ('pawn','king','full') else m['weights'][:8]
        # v1 encoding remains byte-compatible; v2 enabled with the expanded engine.
        text=encode_model(w,sha256(Path(dataset)/'manifest.json'),sha256(Path(dataset)/'splits.json'))
        if name == 'frozen_r3':
            # Preserve the original training provenance and exact deployed bytes.
            text=(ROOT/'experiments/results/r3-model-v1/model.txt').read_text(encoding='ascii')
            m['origin']='frozen R3 model; no R4 fitting or provenance repacking'
        (output/f'{name}.txt').write_bytes(text.encode('ascii'))
        m['model_file']=f'{name}.txt';m['model_sha256']=sha256(output/f'{name}.txt')
    selection={'kind':'r4-study','status':'development-frozen','seed':SEED,'expanded':expanded,
        'dataset':str(dataset),'features':str(features),'feature_provenance':provenance,
        'protocol_sha256':sha256(ROOT/'docs/r4/protocol.md'),'code':git_state(ROOT),'environment':{**hardware(), 'numpy':np.__version__, 'scipy':importlib.metadata.version('scipy')},
        'configuration':{'lambdas':LAMBDAS[1:],'tau':TAU,'intercept':0,'loss':'equal-game fractional BCE',
            'rms':'train-only equal-game RMS, no centering','prior':'handcrafted padded zero',
            'optimizer':'L-BFGS-B','maxiter':1000,'gtol':1e-9,'ftol':1e-12},
        'models':models,'primary_metric':'equal-game BCE','test_evaluated':False}
    write_json(output/'selection.json',selection)
    return selection


class R4Trainer:
    """Existing Trainer.fit boundary for the grouped, calibrated study."""
    def __init__(self, feature_manifest, expanded=False):
        self.feature_manifest=Path(feature_manifest)
        self.expanded=expanded

    def fit(self, spec: TrainingSpec, output_directory: str) -> str:
        version='interpretable-v2' if self.expanded else 'handcrafted-v1'
        dataset=Path(spec.dataset_manifest).parent
        if (spec.features!=version or spec.target!='white-game-result' or spec.seed!=SEED
                or Path(spec.split_manifest).resolve()!=(dataset/'splits.json').resolve()):
            raise ValueError('R4 TrainingSpec mismatch')
        fit(dataset,self.feature_manifest.parent,output_directory,self.expanded)
        return str(Path(output_directory)/'selection.json')


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--dataset',default='experiments/results/r4-data-v1')
    p.add_argument('--features',default='experiments/results/r4-features-v1')
    p.add_argument('--output',required=True)
    p.add_argument('--expanded',action='store_true')
    a=p.parse_args()
    manifest=R4Trainer(Path(a.features)/'manifest.json',a.expanded).fit(
        TrainingSpec(str(Path(a.dataset)/'manifest.json'),'interpretable-v2' if a.expanded else 'handcrafted-v1',
                     SEED,'white-game-result',str(Path(a.dataset)/'splits.json')),a.output)
    s=json.loads(Path(manifest).read_text())
    print(json.dumps({k:{'validation':v['validation'],'hash':v['model_sha256']} for k,v in s['models'].items()},indent=2))

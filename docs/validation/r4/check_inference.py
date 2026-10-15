import gzip,json,math,subprocess
from pathlib import Path
from ucl.records import sha256,write_json
root=Path.cwd();study=root/'experiments/results/r4-models-v1'
selection=json.loads((study/'selection.json').read_text())
rows=[json.loads(s) for s in gzip.decompress((root/'experiments/results/r4-features-v2/features.jsonl.gz').read_bytes()).decode().splitlines()]
fens='\n'.join(r['fen'] for r in rows)+'\n';results={}
for name in ('refit8','pawn','king','full'):
 m=selection['models'][name]
 p=subprocess.run([str(root/'build/release/ucl'),'--infer',str(study/m['model_file']),m['model_sha256']],input=fens,capture_output=True,text=True,check=True,timeout=120)
 actual=[json.loads(s) for s in p.stdout.splitlines()]
 assert len(actual)==len(rows)
 error=0.
 for r,a in zip(rows,actual,strict=True):
  score=sum(w*x for w,x in zip(m['weights'],r['features'],strict=True))
  error=max(error,abs(a['white_score']-score))
  expected=math.floor(abs(score)+.5)*(1 if score>=0 else -1)*(1 if r['fen'].split()[1]=='w' else -1)
  assert a['score_cp']==expected and a['model_sha256']==m['model_sha256']
 assert error<1e-9
 results[name]={'positions':len(rows),'max_absolute_cp_error':error,'rounded_cp_all_equal':True,'model_sha256':m['model_sha256']}
write_json(root/'.tools/r4-expanded-build/inference.json',{'build_info':json.loads(subprocess.check_output([str(root/'build/release/ucl'),'--build-info'],text=True)),'binary_sha256':sha256(root/'build/release/ucl'),'models':results})
print(json.dumps(results,indent=2))

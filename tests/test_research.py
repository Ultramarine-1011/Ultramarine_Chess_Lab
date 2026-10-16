import io
from pathlib import Path
import unittest

import chess
import chess.pgn

from ucl.dataset import prepare, position_key, split_for
from ucl.report import CheckedGameBuilder, check_game_result


class R6TargetTests(unittest.TestCase):
    def test_teacher_perspectives_and_mate(self):
        import chess.engine
        from ucl.r6_data import teacher_record
        for turn in chess.COLORS:
            b = chess.Board()
            b.turn = turn
            r = teacher_record(b, {'score': chess.engine.PovScore(chess.engine.Cp(200), turn)})
            self.assertEqual(r['white_cp'], 200 if turn else -200)
            self.assertEqual(r['stm_cp'], 200)
            self.assertGreater(r['target'] if turn else 1-r['target'], .5)
            m = teacher_record(b, {'score': chess.engine.PovScore(chess.engine.Mate(2), turn)})
            self.assertIsNone(m['white_cp'])
            self.assertEqual(m['target'], float(turn))
        with self.assertRaises(ValueError):
            teacher_record(chess.Board(), {'score': chess.engine.PovScore(chess.engine.Cp(200), True), 'lowerbound': True})
        with self.assertRaises(ValueError):
            teacher_record(chess.Board(), {})

    def test_terminal_and_black_root_ranking(self):
        from ucl.r6_data import teacher_record
        from ucl.r6_training import rank_values, rank_metrics
        b = chess.Board('7k/6Q1/5K2/8/8/8/8/8 b - - 0 1')
        t = teacher_record(b)
        self.assertEqual((t['kind'], t['target'], t['white_order']), ('terminal', 1., 100000))
        children = [{'root_id': 'black', 'game_id': 'g', 'root_turn': False,
                     'move': m, 'features': [cp], 'teacher_evaluation': {'white_order': cp, 'kind': 'cp'}}
                    for m, cp in [('a7a6', 100), ('b7b6', -200), ('c7c6', -200)]]
        values = rank_values(children, [1.])
        self.assertEqual(values[0]['selected_move'], 'b7b6')
        self.assertEqual(rank_metrics(values)['primary_accuracy'], 1.)
        self.assertEqual(rank_metrics(rank_values(children, [0.]))['primary_accuracy'], .5)

    def test_temporal_split_and_child_candidate_set(self):
        from ucl.r6_data import ranking_rows, split
        self.assertEqual(split({'UCLSourceMonth': '2018-04'}, 'x'), 'test')
        b = chess.Board()
        roots = [{'position_id': 'p', 'game_id': 'g', 'split': 'validation', 'fen': b.fen()}]
        children = ranking_rows(roots, 'validation')
        self.assertEqual({r['move'] for r in children}, {m.uci() for m in b.legal_moves})
        self.assertTrue(all(chess.Board(r['fen']).turn == chess.BLACK for r in children))
        self.assertEqual(ranking_rows(roots, 'test'), [])


class DatasetTests(unittest.TestCase):
    def test_reproducibility_and_dedup(self):
        text = (Path(__file__).parent / 'fixtures/data-games.pgn').read_text()
        rows, games, counts = prepare(text)
        self.assertTrue(rows)
        self.assertEqual({r['fen'].split()[1] for r in rows}, {'w', 'b'})
        self.assertEqual((rows, games, counts), prepare(text))
        self.assertEqual(len({r['position_id'] for r in rows}), len(rows))
        self.assertEqual({r['label'] for r in rows}, {0., 0.5, 1.})
        for r in rows:
            self.assertEqual(r['split'], games[r['game_id']]['split'])
            self.assertEqual(r['split'], split_for(r['game_id']))
        duplicated = prepare(text + text)
        self.assertEqual(duplicated[0], rows)
        self.assertGreater(duplicated[2]['duplicate_game'], 0)

    def test_position_identity(self):
        b = chess.Board()
        self.assertEqual(position_key(b), position_key(b.mirror()))
        b.fullmove_number = 99
        self.assertEqual(position_key(b), position_key(chess.Board()))
        b.remove_piece_at(chess.A2)
        white_key = position_key(b)
        b.turn = chess.BLACK
        self.assertNotEqual(position_key(b), white_key)

    def test_natural_vs_external_result(self):
        def game(moves, result, termination):
            return chess.pgn.read_game(io.StringIO(
                f'[Result "{result}"]\n[Termination "{termination}"]\n\n{moves} {result}\n'), Visitor=CheckedGameBuilder)
        for result in ('1-0', '0-1', '1/2-1/2'):
            with self.assertRaisesRegex(ValueError, 'natural termination'):
                check_game_result(game('1. e4', result, 'normal'), True)
            check_game_result(game('1. e4', result, 'adjudication'), True)
        check_game_result(game('1. f3 e5 2. g4 Qh4#', '0-1', 'normal'), True)
        with self.assertRaisesRegex(ValueError, 'terminal board'):
            check_game_result(game('1. f3 e5 2. g4 Qh4#', '1-0', 'adjudication'), True)
        # Lichess Normal also includes resignation, so training uses forced checks.
        check_game_result(game('1. e4', '1-0', 'Normal'))





class FeatureTests(unittest.TestCase):
    def test_cpp_consistency(self):
        import json
        import os
        import random
        from ucl.feature_data import extract
        engine = os.environ.get('UCL_ENGINE', str(Path(__file__).resolve().parents[1] / 'build/release/ucl'))
        root = Path(__file__).resolve().parents[1]
        fens = [p['fen'] for p in json.loads((root / 'experiments/positions/r2-v1.json').read_text())['positions']]
        rng, b = random.Random(20261015), chess.Board()
        for _ in range(120):
            if b.is_game_over(): b = chess.Board()
            b.push(rng.choice(list(b.legal_moves)))
            fens.extend([b.fen(), b.mirror().fen()])
        records = extract(engine, fens)
        self.assertEqual(len(records), len(fens))
        for i in range(10, len(records), 2):
            self.assertEqual(records[i]['features'], [-x for x in records[i+1]['features']])
            self.assertEqual(records[i]['handcrafted_cp'], records[i+1]['handcrafted_cp'])
        import subprocess
        self.assertNotEqual(subprocess.run([engine, '--features'], input='invalid fen\n', text=True, capture_output=True).returncode, 0)

    def test_input_errors(self):
        from ucl.feature_data import validate_vector
        from copy import deepcopy
        valid = {'feature_version': 'handcrafted-v1', 'features': [0]*8, 'handcrafted_cp': 0}
        for key, value in [('features', [0]*7), ('features', [float('nan')]*8), ('features', [float('inf')]*8), ('features', [True]*8), ('feature_version', 'v2')]:
            bad = deepcopy(valid); bad[key] = value
            with self.assertRaises(ValueError): validate_vector(bad)





class TrainingTests(unittest.TestCase):
    def test_gradient_stability_and_fit(self):
        import numpy as np
        from ucl.training import objective, optimize, metrics, check_arrays
        from ucl.feature_data import WEIGHTS
        rng = np.random.default_rng(123)
        x = rng.normal(size=(40, 8))
        y = np.array([0., .5, 1., .5]*10)
        beta, prior = rng.normal(size=8), np.zeros(8)
        value, gradient = objective(beta, x, y, prior, .1)
        numeric = np.empty(8)
        for i in range(8):
            d = np.zeros(8); d[i] = 1e-5
            numeric[i] = (objective(beta+d,x,y,prior,.1)[0]-objective(beta-d,x,y,prior,.1)[0])/2e-5
        np.testing.assert_allclose(gradient,numeric,atol=1e-9)
        self.assertTrue(np.isfinite(objective(beta*1e5, x, y, prior, 0)[0]))
        a, b = optimize(x,y,.01), optimize(x,y,.01)
        self.assertTrue(a['success'])
        self.assertEqual(a['weights'], b['weights'])
        self.assertLess(metrics(x,y,a['weights'])['bce'], metrics(x,y,WEIGHTS)['bce'])
        for xx, yy in [(x[:,:7], y), (x, y[:-1]), (x*np.nan,y), (x,y+1)]:
            with self.assertRaises(ValueError): check_arrays(xx,yy)

    def test_strict_model_format(self):
        import tempfile
        from ucl.model import encode_model, load_model
        from ucl.records import sha256
        weights = [100.,320.,330.,500.,900.,5.,4.,30.]
        text = encode_model(weights,'a'*64,'b'*64)
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)/'model.txt'; p.write_bytes(text.encode())
            self.assertEqual(load_model(p,sha256(p)),weights)
            with self.assertRaises(ValueError): load_model(p,'0'*64)
            for corrupt in [text+'extra', text.replace('handcrafted-v1','v2'), text.replace('weights 8','weights 7'),text.replace('100 320','nan 320'),text.replace('intercept 0','intercept 1')]:
                p.write_bytes(corrupt.encode())
                with self.assertRaises(ValueError): load_model(p,sha256(p))
        for w in [weights[:-1], [float('inf')]*8, [10001]*8]:
            with self.assertRaises(ValueError): encode_model(w,'a'*64,'b'*64)

    def test_selection_never_evaluates_test(self):
        import tempfile
        from unittest.mock import patch
        import ucl.training as training
        root = Path(__file__).resolve().parents[1]
        spec = training.TrainingSpec(str(root/'experiments/results/r3-data-v2/manifest.json'),
            'handcrafted-v1',20261015,'white-game-result',str(root/'experiments/results/r3-data-v2/splits.json'))
        original = training.arrays
        def guard(rows, split):
            self.assertNotEqual(split,'test')
            return original(rows,split)
        with tempfile.TemporaryDirectory() as tmp, patch('ucl.training.arrays',side_effect=guard):
            p = training.fit(root/'experiments/results/r3-features-v2/manifest.json',spec,str(Path(tmp)/'fit'))
            m = training.validate_model_manifest(p)
            self.assertEqual(m['status'],'frozen')
            self.assertFalse((Path(p).parent/'test-results.json').exists())
            # An ordinary development fit can be repeated without a new directory.
            training.fit(root/'experiments/results/r3-features-v2/manifest.json',spec,str(Path(tmp)/'fit'))
            (Path(p).parent/'test-results.json').write_text('{}')
            with self.assertRaisesRegex(ValueError,'held-out'):
                training.fit(root/'experiments/results/r3-features-v2/manifest.json',spec,str(Path(tmp)/'fit'))





class InferenceTests(unittest.TestCase):
    def test_cpp_python_real_model(self):
        import gzip, json, math, os, subprocess
        import numpy as np
        from ucl.model import load_model
        root = Path(__file__).resolve().parents[1]
        engine = os.environ.get('UCL_ENGINE', str(root/'build/release/ucl'))
        model = root/'experiments/results/r3-model-v1/model.txt'
        m = json.loads(model.with_name('model-manifest.json').read_text())
        weights = load_model(model,m['model_sha256'])
        rows = [json.loads(x) for x in gzip.decompress((root/'experiments/results/r3-features-v2/features.jsonl.gz').read_bytes()).decode().splitlines()]
        fens = [r['fen'] for r in rows]
        p = subprocess.run([engine,'--infer',str(model),m['model_sha256']],input='\n'.join(fens)+'\n',capture_output=True,text=True,check=True,timeout=60)
        actual = [json.loads(line) for line in p.stdout.splitlines()]
        self.assertEqual(len(actual),len(rows))
        for r,a in zip(rows,actual):
            score = sum(w*x for w,x in zip(weights,r['features']))
            self.assertAlmostEqual(a['white_score'],score,places=9)
            cp = math.floor(abs(score)+.5)*(1 if score>=0 else -1)
            self.assertEqual(a['score_cp'],cp*(1 if r['fen'].split()[1]=='w' else -1))
            self.assertEqual(a['model_sha256'],m['model_sha256'])

    def test_cpp_schema_hash_and_rounding(self):
        import os, subprocess, tempfile
        from ucl.model import encode_model
        from ucl.records import sha256
        engine = os.environ.get('UCL_ENGINE',str(Path(__file__).resolve().parents[1]/'build/release/ucl'))
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)/'model with spaces.txt'
            text = encode_model([.5,0,0,0,0,0,0,0],'a'*64,'b'*64)
            fens = ['4k3/8/8/8/8/8/P7/4K3 w - - 0 1','4k3/8/8/8/8/8/P7/4K3 b - - 0 1', '4k3/p7/8/8/8/8/8/4K3 w - - 0 1']
            p.write_bytes(text.encode())
            result = subprocess.run([engine,'--infer',str(p),sha256(p)],input='\n'.join(fens)+'\n',capture_output=True,text=True,check=True)
            import json
            self.assertEqual([json.loads(x)['score_cp'] for x in result.stdout.splitlines()],[1,-1,-1])
            from ucl.feature_data import WEIGHTS, extract
            baseline_text=encode_model(WEIGHTS,'a'*64,'b'*64)
            p.write_bytes(baseline_text.encode())
            baseline=subprocess.run([engine,'--infer',str(p),sha256(p)],input='\n'.join(fens)+'\n',capture_output=True,text=True,check=True)
            self.assertEqual([json.loads(x)['score_cp'] for x in baseline.stdout.splitlines()], [r['handcrafted_cp'] for r in extract(engine,fens)])
            for corrupt in [text+'extra',text.replace('weights 8','weights 7'),text.replace('handcrafted-v1','wrong'),text.replace('0.5 0','nan 0'),text.replace('0.5 0','inf 0'),text.replace('0.5 0','10001 0'),text.replace('intercept 0','intercept 1'), 'x'*4097, '']:
                p.write_bytes(corrupt.encode())
                q = subprocess.run([engine,'--infer',str(p),sha256(p)],input=fens[0]+'\n',capture_output=True,text=True)
                self.assertNotEqual(q.returncode,0)
                self.assertIn('model rejected',q.stderr)
            p.write_bytes(text.encode())
            self.assertNotEqual(subprocess.run([engine,'--infer',str(p),'0'*64],capture_output=True).returncode,0)



class R4DataTests(unittest.TestCase):
    def test_temporal_plan_and_r3_compatibility(self):
        from ucl.r4_data import annotated, temporal_split, diagnostics
        from ucl.dataset import validate_dataset
        text=(Path(__file__).parent/'fixtures/data-games.pgn').read_text()
        a=annotated(text,'2017-02')
        rows,games,counts=prepare(a,split_resolver=temporal_split,metadata=True)
        self.assertTrue(rows)
        self.assertTrue(all(g['split']!='test' for g in games.values()))
        rows2,games2,_=prepare(annotated(text,'2017-06'),split_resolver=temporal_split,metadata=True)
        self.assertEqual({r['split'] for r in rows2},{'test'})
        self.assertEqual(set(games),set(games2))
        self.assertEqual(set(r['position_id'] for r in rows),set(r['position_id'] for r in rows2))
        self.assertFalse(diagnostics(rows,games)['strict_temporal_separation'])
        for name in ('r3-data-v1','r3-data-v2'):
            validate_dataset(Path(__file__).resolve().parents[1]/'experiments/results'/name)
        with self.assertRaises(ValueError): temporal_split({'UCLSourceMonth':'2017-09'},'a'*64)

class R4TrainingTests(unittest.TestCase):
    def test_equal_game_and_weighted_gradient(self):
        import numpy as np
        from ucl.r4_training import arrays, metrics
        from ucl.training import objective
        rows=[{'split':'train','game_id':g,'features':[v]*8,'label':y}
              for g,v,y in [('a',1,1.),('a',2,1.),('b',3,0.)]]
        _,x,y,q=arrays(rows,'train')
        np.testing.assert_allclose(q,[.25,.25,.5])
        beta=np.arange(8)*.03;prior=np.zeros(8)
        value,gradient=objective(beta,x,y,prior,.01,q)
        numeric=[]
        for i in range(8):
            d=np.zeros(8);d[i]=1e-5
            numeric.append((objective(beta+d,x,y,prior,.01,q)[0]-objective(beta-d,x,y,prior,.01,q)[0])/2e-5)
        np.testing.assert_allclose(gradient,numeric,atol=1e-9)
        self.assertTrue(np.isfinite(value))

    def test_fit_never_evaluates_test(self):
        import json, tempfile
        import numpy as np
        from unittest.mock import patch
        import ucl.r4_training as study
        rng=np.random.default_rng(42)
        rows=[{'split':split,'game_id':f'{split}-{i//2}','features':rng.normal(size=8).tolist(),
               'label':float(i%2),'position_id':f'{split}-{i}'}
              for split in ('train','validation','test') for i in range(24)]
        original=study.arrays
        def guard(rows,split):
            self.assertNotEqual(split,'test')
            return original(rows,split)
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);(p/'manifest.json').write_text('{}');(p/'splits.json').write_text('{}')
            with patch.object(study,'read_rows',return_value=(rows,{})), patch.object(study,'arrays',side_effect=guard):
                result=study.fit(p,p,p/'output')
            self.assertFalse(result['test_evaluated'])
            self.assertGreater(result['models']['calibration']['scale'],0)
            self.assertEqual(set(result['models']),{'handcrafted','calibration','frozen_r3','refit8'})
            self.assertFalse((p/'output/test-results.json').exists())

class R4FeatureTests(unittest.TestCase):
    def test_v2_reference_symmetry_and_boundaries(self):
        import os, random, json
        from ucl.r4_features import extract, reference
        engine=os.environ.get('UCL_ENGINE',str(Path(__file__).resolve().parents[1]/'build/release/ucl'))
        fens=[p['fen'] for p in json.loads((Path(__file__).resolve().parents[1]/'experiments/positions/r2-v1.json').read_text())['positions']]
        # Isolated/doubled and advanced/passed pawns; shield/attacks; promotion-rich
        # material clamps phase, and bare kings test the full endgame numerator.
        fens += ['4k3/8/8/2p5/2P5/P7/P7/4K3 w - - 0 1',
                 '4k3/P7/8/8/8/8/5PPP/6K1 w - - 0 1',
                 '4k3/8/8/8/8/8/8/3K4 w - - 0 1',
                 'q2qk2q/8/8/8/8/8/8/Q2QK2Q w - - 0 1']
        # The promotion-rich board must be legal: opponent king not attacked.
        fens[-1]='qqqqk3/8/8/8/8/8/8/QQQ1K3 w - - 0 1'
        rng=random.Random(20261015);b=chess.Board()
        for _ in range(200):
            if b.is_game_over():b=chess.Board()
            b.push(rng.choice(list(b.legal_moves)));fens.append(b.fen())
        pairs=[f for fen in fens for f in (fen,chess.Board(fen).mirror().fen())]
        actual=extract(engine,pairs)
        for i in range(0,len(actual),2):
            self.assertEqual(actual[i]['features'],[-x for x in actual[i+1]['features']])
        f=reference(chess.Board(fens[10]))
        self.assertEqual(f[8:11],[2.,1.,1.])
        self.assertEqual(reference(chess.Board('4k3/8/8/8/3K4/8/8/8 w - - 0 1'))[13],72.)
        self.assertEqual(reference(chess.Board('4k3/8/8/8/8/8/5PPP/6K1 w - - 0 1'))[11],3.)
        self.assertEqual(reference(chess.Board('4k1r1/8/8/8/8/8/8/6K1 w - - 0 1'))[12],1.)
        self.assertEqual(reference(chess.Board('qqqqk3/8/8/8/8/8/8/QQQ1K3 w - - 0 1'))[13],0.)
        self.assertEqual(reference(chess.Board())[8:],[0.]*6)

    def test_v2_model_parity_and_errors(self):
        import json, math, os, subprocess, tempfile
        from ucl.r4_features import reference
        from ucl.model import encode_model,load_model
        from ucl.records import sha256
        engine=os.environ.get('UCL_ENGINE',str(Path(__file__).resolve().parents[1]/'build/release/ucl'))
        fens=['4k3/8/8/2p5/2P5/P7/P7/4K3 w - - 0 1',
              '4k3/8/8/8/8/8/P7/4K3 b - - 0 1',chess.STARTING_FEN]
        weights=[100,320,330,500,900,5,4,30,-12,-7,8,11,-9,.125]
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'v2 model.txt';text=encode_model(weights,'a'*64,'b'*64);p.write_bytes(text.encode())
            self.assertEqual(load_model(p,sha256(p)),weights)
            raw=subprocess.run([engine,'--infer',str(p),sha256(p)],input='\n'.join(fens)+'\n',capture_output=True,text=True,check=True)
            for fen,r in zip(fens,map(json.loads,raw.stdout.splitlines())):
                score=sum(a*b for a,b in zip(weights,reference(chess.Board(fen))))
                self.assertAlmostEqual(r['white_score'],score)
                self.assertEqual(r['score_cp'],math.floor(abs(score)+.5)*(1 if score>=0 else -1)*(1 if chess.Board(fen).turn else -1))
            for bad in (text.replace('interpretable-v2','handcrafted-v1'),text.replace('ucl-linear-v2','ucl-linear-v1'),
                        text.replace('weights 14','weights 8'),text.replace('0.125','nan'),text+'extra'):
                p.write_bytes(bad.encode())
                with self.assertRaises(ValueError):load_model(p,sha256(p))
                self.assertNotEqual(subprocess.run([engine,'--infer',str(p),sha256(p)],capture_output=True).returncode,0)


class R4AnalysisTests(unittest.TestCase):
    def test_game_bootstrap_and_exclusive_test_gate(self):
        import json, tempfile
        import numpy as np
        from unittest.mock import patch
        from ucl.r4_analysis import game_means,paired_interval,evaluate
        from ucl.records import sha256
        from ucl.model import encode_model
        rows=[{'game_id':g} for g in ('a','a','b')]
        np.testing.assert_allclose(game_means([0,2,4],rows),[1,4])
        interval=paired_interval(np.array([0,2,4]),rows,np.array([[0,0],[1,1],[0,1]]))
        self.assertEqual(interval['difference'],2.5)
        self.assertEqual(interval['position_weighted_difference'],2.)
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);models={}
            for name in ('handcrafted','calibration','frozen_r3','refit8','pawn','king','full'):
                weights=[100,320,330,500,900,5,4,30]+[0]*6
                path=p/(name+'.txt');path.write_bytes(encode_model(weights,'a'*64,'b'*64).encode())
                models[name]={'weights':weights,'model_file':path.name,'model_sha256':sha256(path)}
            games={'a':{'month':'2017-06'},'b':{'month':'2017-07'}}
            (p/'splits.json').write_text(json.dumps(games))
            selection={'models':models,'dataset':str(p),'features':str(p)}
            (p/'selection.json').write_text(json.dumps(selection))
            freeze={'selection_sha256':sha256(p/'selection.json'),'models':{n:m['model_sha256'] for n,m in models.items()},'candidate':'full'}
            (p/'freeze.json').write_text(json.dumps(freeze))
            # A leftover start marker from an interrupted evaluation does not
            # prevent completing the same fixed-model held-out calculation.
            (p/'test-evaluation.started.json').write_text('{}')
            data=[{'split':'test','game_id':g,'position_id':str(i),'ply':16+i*7,
                   'features':[0]*14,'label':float(i%2),'fen':chess.STARTING_FEN}
                  for i,g in enumerate(('a','a','b'))]
            with patch('ucl.r4_analysis.read_rows',return_value=(data,{})):
                result=evaluate(p,p/'freeze.json')
                self.assertEqual(result['games'],2)
                self.assertAlmostEqual(result['models']['handcrafted']['equal_game']['bce'],np.log(2))
                with self.assertRaises(FileExistsError):evaluate(p,p/'freeze.json')
            before=(p/'test-results.json').read_bytes()
            (p/'full.txt').write_bytes(b'tampered')
            with self.assertRaises(ValueError):evaluate(p,p/'freeze.json')
            self.assertEqual(before,(p/'test-results.json').read_bytes())


class R4OpeningTests(unittest.TestCase):
    def test_identity_selection_and_exclusions(self):
        from ucl.r4_openings import select
        text=(Path(__file__).parent/'fixtures/data-games.pgn').read_text()
        a,counts=select(text,2,set())
        self.assertEqual(len(a),2)
        self.assertEqual(a,select(text,2,set())[0])
        self.assertEqual(len({r['position_id'] for r in a}),2)
        excluded={r['position_id'] for r in a}
        b,_=select(text,2,excluded)
        self.assertFalse(excluded & {r['position_id'] for r in b})
        c,_=select(text,2,set(),{r['game_id'] for r in a})
        self.assertFalse({r['game_id'] for r in a}&{r['game_id'] for r in c})
        for r in a:
            board=chess.Board()
            for move in r['moves']:board.push_uci(move)
            self.assertEqual(board.fen(),r['fen'])


class R4SelectionTests(unittest.TestCase):
    def test_selection_uses_validation_and_cost_gate(self):
        from ucl.r4_experiment import choose,GROUPS
        models={n:{'success':True,'active':list(range(8+i)),
                   'validation':{'equal_game':{'bce':.6-i*.001}},'test':{'bce':i}}
                for i,n in enumerate(GROUPS)}
        self.assertEqual(choose(models,{n:1 for n in GROUPS}),'full')
        self.assertEqual(choose(models,{'refit8':1,'pawn':1,'king':1,'full':11}),'king')
        models['king']['success']=False
        self.assertEqual(choose(models,{'refit8':1,'pawn':1,'king':1,'full':11}),'pawn')
        with self.assertRaises(ValueError):choose(models,{n:11 for n in GROUPS})


class R4RecoveryTests(unittest.TestCase):
    def test_fixed_opening_suffix_combination(self):
        import tempfile
        from ucl.r4_study import combine
        source=Path(__file__).resolve().parents[1]/'experiments/results/r4-telemetry-smoke/games.pgn'
        games=[]
        with source.open() as stream:
            while (g:=chess.pgn.read_game(stream)) is not None:games.append(g)
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);sources=[];lines=[]
            for part in range(2):
                group=games[2*part:2*part+2]
                lines.append(group[0].board().epd())
                for g in group:g.headers['Round']='1'
                path=p/f'{part}.pgn';path.write_text('\n\n'.join(str(g) for g in group))
                sources.append((path,part,2))
            combine(sources,lines,p/'combined.pgn')
            text=(p/'combined.pgn').read_text()
            self.assertEqual(text.count('[Round "1"]'),2)
            self.assertEqual(text.count('[Round "2"]'),2)
            with self.assertRaises(ValueError):combine(sources,lines[::-1],p/'bad.pgn')

if __name__ == '__main__':
    unittest.main()

import io
from pathlib import Path
import unittest

import chess
import chess.pgn

from ucl.dataset import prepare, position_key, split_for
from ucl.report import CheckedGameBuilder, check_game_result


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
            p = training.LinearTrainer(root/'experiments/results/r3-features-v2/manifest.json').fit(spec,str(Path(tmp)/'fit'))
            m = training.validate_model_manifest(p)
            self.assertEqual(m['status'],'frozen')
            self.assertFalse((Path(p).parent/'test-results.json').exists())





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


if __name__ == '__main__':
    unittest.main()

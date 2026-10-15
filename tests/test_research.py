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


if __name__ == '__main__':
    unittest.main()

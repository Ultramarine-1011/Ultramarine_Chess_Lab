"""Black-box UCI tests, including real pipe timing and independent move validation."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import queue
import random
import subprocess
import sys
import threading
import time
import unittest

import chess
import chess.engine

ENGINE = sys.argv.pop(1)


class Pipe:
    def __init__(self):
        self.p = subprocess.Popen([ENGINE], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, text=True, bufsize=1)
        self.lines = queue.Queue()
        self.reader = threading.Thread(target=self.read, daemon=True)
        self.reader.start()

    def read(self):
        for line in self.p.stdout:
            self.lines.put(line.strip())

    def send(self, line):
        self.p.stdin.write(line + "\n")
        self.p.stdin.flush()

    def until(self, prefix, timeout=5):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            line = self.lines.get(timeout=max(0.001, end - time.monotonic()))
            if line.startswith(prefix):
                return line
        raise TimeoutError(prefix)

    def close(self):
        try:
            self.send("quit")
            self.p.wait(timeout=3)
            if self.p.returncode:
                raise AssertionError(self.p.stderr.read())
        finally:
            if self.p.poll() is None:
                self.p.kill()
                self.p.wait()
            self.reader.join(timeout=1)
            for stream in (self.p.stdin, self.p.stdout, self.p.stderr):
                stream.close()


class UciTests(unittest.TestCase):
    def setUp(self):
        self.pipe = Pipe()
        self.addCleanup(self.pipe.close)
        self.pipe.send("uci")
        self.pipe.until("uciok")

    def test_linear_loading_switch_and_lifecycle(self):
        root = Path(__file__).resolve().parents[1]
        model = root/'experiments/results/r3-model-v1/model.txt'
        m = json.loads(model.with_name('model-manifest.json').read_text())
        p = self.pipe
        def identity():
            p.send('evalinfo')
            return json.loads(p.until('info string ucl_evaluator ').removeprefix('info string ucl_evaluator '))
        self.assertEqual(identity(),{'evaluator':'handcrafted-v1','model_sha256':None})
        p.send('setoption name Evaluator value Linear')
        p.until('info string command rejected:')
        p.send('setoption name ModelSHA256 value '+m['model_sha256'])
        p.send('setoption name ModelFile value '+str(model))
        p.until('info string model loaded')
        p.send('setoption name Evaluator value Linear')
        expected={'evaluator':'linear-v1','model_sha256':m['model_sha256']}
        self.assertEqual(identity(),expected)
        p.send('position fen 4k3/8/8/8/8/8/3Q4/4K3 w - - 0 1')
        p.send('eval')
        value=json.loads(p.until('info string ucl_eval ').removeprefix('info string ucl_eval '))
        self.assertEqual(value['score_cp'],1004)
        p.send('setoption name ModelFile value /missing/model.txt')
        p.until('info string command rejected:')
        self.assertEqual(identity(),expected)
        p.send('setoption name ModelSHA256 value '+'0'*64)
        p.send('setoption name ModelFile value '+str(model))
        p.until('info string command rejected:')
        self.assertEqual(identity(),expected)
        p.send('setoption name ModelSHA256 value '+m['model_sha256'])
        p.send('position startpos'); p.send('go infinite'); p.until('info depth 1')
        p.send('setoption name ModelFile value '+str(model))
        p.until('bestmove'); p.until('info string model loaded')
        self.assertEqual(identity(),expected)
        p.send('go infinite'); p.until('info depth 1')
        p.send('setoption name Evaluator value Handcrafted');p.until('bestmove')
        self.assertEqual(identity(),{'evaluator':'handcrafted-v1','model_sha256':None})
        p.send('setoption name Evaluator value Linear')
        p.send('position fen 7k/6Q1/6K1/8/8/8/8/8 b - - 0 1')
        p.send('go depth 1');self.assertEqual(p.until('bestmove'),'bestmove 0000')

    def test_async_ready_stop_and_restart(self):
        p = self.pipe
        p.send("position startpos")
        p.send("go infinite")
        p.until("info depth 2")
        p.send("isready")
        self.assertEqual(p.until("readyok", 2), "readyok")
        p.send("stop")
        best = p.until("bestmove", 2).split()[1]
        self.assertIn(chess.Move.from_uci(best), chess.Board().legal_moves)
        p.send("ucinewgame")
        p.send("position startpos moves e2e4")
        p.send("go depth 2")
        best = p.until("bestmove").split()[1]
        board = chess.Board(); board.push_uci("e2e4")
        self.assertIn(chess.Move.from_uci(best), board.legal_moves)

    def test_time_and_nodes(self):
        for command in ("go movetime 40", "go nodes 50", "go wtime 10 btime 10", "go depth 1"):
            start = time.monotonic()
            self.pipe.send(command)
            best = self.pipe.until("bestmove", 3).split()[1]
            self.assertIn(chess.Move.from_uci(best), chess.Board().legal_moves)
            self.assertLess(time.monotonic() - start, 3)

    def test_terminal_and_invalid_commands(self):
        p = self.pipe
        p.send("position fen 7k/6Q1/6K1/8/8/8/8/8 b - - 0 1")
        for bad in ("position startpos moves e2e5", "position fen nonsense", "position"):
            p.send(bad)
            p.until("info string position rejected:")
            p.send("go depth 1")
            self.assertEqual(p.until("bestmove"), "bestmove 0000")
        for bad in ("go depth", "go nodes -2", "go movetime bananas", "go depth 0"):
            p.send(bad)
            p.until("info string command rejected:")
        p.send("isready")
        self.assertEqual(p.until("readyok"), "readyok")

    def test_quit_during_search_and_eof(self):
        for shutdown in ("quit", None):
            other = Pipe()
            other.send("go infinite")
            other.until("info depth 1")
            if shutdown:
                other.send(shutdown)
            else:
                other.p.stdin.close()
            other.p.wait(timeout=3)
            self.assertEqual(other.p.returncode, 0)
            other.reader.join(timeout=1)
            for stream in (other.p.stdin, other.p.stdout, other.p.stderr):
                stream.close()

    def test_python_chess_client(self):
        with chess.engine.SimpleEngine.popen_uci(ENGINE, timeout=5) as engine:
            engine.configure({"MoveOverhead": 0})
            board = chess.Board()
            for _ in range(16):
                result = engine.play(board, chess.engine.Limit(depth=2))
                self.assertIn(result.move, board.legal_moves)
                board.push(result.move)
                if board.is_game_over():
                    break

    def test_search_option_combinations(self):
        with chess.engine.SimpleEngine.popen_uci(ENGINE, timeout=5) as engine:
            for q in (False, True):
                scores = []
                for tt in (False, True):
                    for pv in (False, True):
                        engine.configure({"Quiescence": q, "UseTT": tt, "PVOrdering": pv, "Hash": 1})
                        board = chess.Board()
                        info = engine.analyse(board, chess.engine.Limit(depth=3))
                        scores.append(info["score"])
                        for move in info["pv"]:
                            self.assertIn(move, board.legal_moves)
                            board.push(move)
                self.assertTrue(all(s == scores[0] for s in scores))
        for bad in ("setoption name Quiescence value yes", "setoption name Hash value 0"):
            self.pipe.send(bad)
            self.pipe.until("info string command rejected:")

    def test_retained_benchmark_and_validation(self):
        from ucl.benchmark import run_benchmark
        from ucl.integrity import validate_bundle
        from ucl.records import write_json
        root = Path(__file__).resolve().parents[1]
        info = json.loads(subprocess.check_output([ENGINE, "--build-info"], text=True))
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            suite = tmp / "suite.json"
            write_json(suite, {"version": 1, "positions": [{"id": "start", "fen": chess.STARTING_FEN}]})
            config = {"version": 1, "seed": 7, "suite": str(suite), "repeats": 2,
                      "limits": [{"depth": 2}, {"nodes": 30}], "engines": [
                          {"name": "test", "path": str(Path(ENGINE).resolve()), "revision": info["revision"],
                           "build": "CTest binary", "ucl_build_info": True,
                           "options": {"Quiescence": True, "UseTT": True, "PVOrdering": True, "Hash": 1}}]}
            source = tmp / "input.json"; write_json(source, config)
            output = tmp / "benchmark"
            record = run_benchmark(root, source, output, allow_dirty=True)
            self.assertEqual(record["status"], "completed", record["error"])
            schema = json.loads((root / "schemas/benchmark-v1.schema.json").read_text())
            validate_bundle(output / "record.json", schema)
            self.assertEqual(len(record["rows"]), 4)
            for row in record["rows"]:
                self.assertEqual(row["counter_scope"], "final")
                if "nodes" in row["limit"]:
                    self.assertEqual(row["nodes"], 30)
            bad = deepcopy(record); bad["summary"][0]["median_nodes_sum"] += 1
            write_json(output / "record.json", bad)
            with self.assertRaisesRegex(ValueError, "summary"):
                validate_bundle(output / "record.json", schema)
            write_json(output / "record.json", record)
            with (output / "uci.log").open("a") as stream:
                stream.write("tamper")
            with self.assertRaisesRegex(ValueError, "integrity"):
                validate_bundle(output / "record.json", schema)

    def test_retained_model_benchmark_identity(self):
        from ucl.benchmark import run_benchmark
        from ucl.integrity import validate_bundle
        from ucl.records import write_json, sha256
        root=Path(__file__).resolve().parents[1]
        model=root/'experiments/results/r3-model-v1/model.txt'
        model_hash=sha256(model)
        info=json.loads(subprocess.check_output([ENGINE,'--build-info'],text=True))
        with tempfile.TemporaryDirectory() as tmp:
            tmp=Path(tmp);suite=tmp/'suite.json'
            write_json(suite,{'version':1,'positions':[{'id':'start','fen':chess.STARTING_FEN}]})
            engines=[]
            for name,opts in [('hand',{'Evaluator':'Handcrafted'}),('linear',{'Evaluator':'Linear','ModelFile':str(model),'ModelSHA256':model_hash})]:
                engines.append({'name':name,'path':str(Path(ENGINE).resolve()),'revision':info['revision'],'build':'CTest binary','ucl_build_info':True,'options':opts})
            config={'version':1,'seed':7,'suite':str(suite),'repeats':1,'limits':[{'depth':1}],'engines':engines}
            source=tmp/'input.json';write_json(source,config)
            out=tmp/'bundle';record=run_benchmark(root,source,out,allow_dirty=True)
            self.assertEqual(record['status'],'completed',record['error'])
            schema=json.loads((root/'schemas/benchmark-v1.schema.json').read_text())
            validate_bundle(out/'record.json',schema)
            self.assertEqual(record['engines'][1]['evaluation']['model_sha256'],model_hash)
            bad=deepcopy(record);bad['engines'][1]['evaluation']['model_sha256']='0'*64
            write_json(out/'record.json',bad)
            with self.assertRaisesRegex(ValueError,'model identity'):validate_bundle(out/'record.json',schema)

    def test_seeded_positions_and_pv(self):
        rng = random.Random(20261015)
        board = chess.Board()
        with chess.engine.SimpleEngine.popen_uci(ENGINE, timeout=5) as engine:
            for _ in range(20):
                for _ in range(3):
                    if board.is_game_over():
                        board = chess.Board()
                    board.push(rng.choice(list(board.legal_moves)))
                info = engine.analyse(board, chess.engine.Limit(depth=2))
                copy = board.copy()
                for move in info.get("pv", []):
                    self.assertIn(move, copy.legal_moves)
                    copy.push(move)


if __name__ == "__main__":
    unittest.main()

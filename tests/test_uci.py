"""Black-box UCI tests, including real pipe timing and independent move validation."""
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

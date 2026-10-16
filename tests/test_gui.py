"""GUI tests use the real UCL UCI executable, never a mock chess rules engine."""
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

import chess
import chess.engine
import chess.pgn

from ucl.gui import GameSession, GuiError, GuiServer, close_engine

ROOT = Path(__file__).resolve().parents[1]
ENGINE = Path(os.environ.get("UCL_ENGINE", ROOT / "build/release" / ("ucl.exe" if os.name == "nt" else "ucl")))


@unittest.skipUnless(ENGINE.is_file(), "Build UCL or set UCL_ENGINE")
class GuiTests(unittest.TestCase):
    def setUp(self):
        self.session = GameSession(ENGINE, seconds=0.01, model_root=ROOT)
        self.addCleanup(self.session.close)

    def action(self, name, **kwargs):
        return self.session.action(name, {"revision": self.session.revision, **kwargs})

    def test_real_move_history_undo_and_pgn(self):
        initial = self.session.state()
        after = self.action("move", move="e2e4")
        self.assertTrue(after["engine_turn"])
        self.assertEqual(after["moves"][0]["san"], "e4")
        after = self.action("engine")
        self.assertEqual(len(after["moves"]), 2)
        self.assertFalse(after["engine_turn"])
        game = chess.pgn.read_game(io.StringIO(self.session.pgn()))
        self.assertEqual(game.errors, [])
        self.assertEqual(game.end().board().fen(), after["fen"])
        after = self.action("undo")
        self.assertEqual(initial["fen"], after["fen"])
        self.assertFalse(after["can_undo"])
        self.assertEqual(after["moves"], [])

    def test_black_opening_and_undo(self):
        state = self.action("new", color="black", seconds=0.01)
        self.assertTrue(state["engine_turn"])
        state = self.action("engine")
        opening = state["fen"]
        self.assertFalse(state["can_undo"])
        with self.assertRaises(GuiError):
            self.action("undo")
        self.action("move", move=state["legal_moves"][0])
        self.action("engine")
        state = self.action("undo")
        self.assertEqual(state["fen"], opening)
        self.assertEqual(state["turn"], "black")

    def test_illegal_null_missing_promotion_and_stale_are_atomic(self):
        before = self.session.state()
        for move in ("e2e5", "e7e5", "0000", "bad", "e1e3", None):
            with self.assertRaises(GuiError):
                self.action("move", move=move)
            self.assertEqual(self.session.state(), before)
        self.action("move", move="e2e4")
        with self.assertRaises(GuiError) as raised:
            self.session.action("move", {"revision": before["revision"], "move": "d2d4"})
        self.assertEqual(raised.exception.status, 409)
        with self.assertRaises(GuiError):
            self.action("move", move="d2d4")

    def test_promotion_all_pieces_and_undo(self):
        for piece in "qnrb":
            self.session.board = chess.Board("7k/P7/8/8/8/8/8/7K w - - 0 1")
            before = self.session.state()
            with self.assertRaises(GuiError):
                self.action("move", move="a7a8")
            self.assertEqual(before, self.session.state())
            state = self.action("move", move="a7a8" + piece)
            self.assertEqual(self.session.board.piece_at(chess.A8).symbol(), piece.upper())
            game = chess.pgn.read_game(io.StringIO(self.session.pgn()))
            self.assertEqual(game.end().board().fen(), state["fen"])
            self.assertEqual(game.headers["SetUp"], "1")
            state = self.action("undo")
            self.assertEqual(state["fen"], before["fen"])

    def test_black_promotion_castling_en_passant(self):
        self.action("new", color="black", seconds=0.01)
        self.session.board = chess.Board("7k/8/8/8/8/8/p7/7K b - - 0 1")
        self.action("move", move="a2a1n")
        self.assertEqual(self.session.board.piece_at(chess.A1).symbol(), "n")
        self.action("new", seconds=0.01)
        self.session.board = chess.Board("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1")
        self.action("move", move="e1g1")
        self.assertEqual(self.session.board.piece_at(chess.F1).symbol(), "R")
        self.session.board = chess.Board("7k/8/8/3pP3/8/8/8/7K w - d6 0 1")
        self.action("move", move="e5d6")
        self.assertIsNone(self.session.board.piece_at(chess.D5))

    def test_endings_and_undo_mate(self):
        fixtures = [
            ("7k/6Q1/5K2/8/8/8/8/8 b - - 0 1", "CHECKMATE", "1-0"),
            ("7k/5K2/6Q1/8/8/8/8/8 b - - 0 1", "STALEMATE", "1/2-1/2"),
            ("7k/8/8/8/8/8/8/7K w - - 0 1", "INSUFFICIENT_MATERIAL", "1/2-1/2"),
            ("7k/8/8/8/8/8/8/R6K w - - 100 51", "FIFTY_MOVES", "1/2-1/2")]
        for fen, termination, result in fixtures:
            self.session.board = chess.Board(fen)
            state = self.session.state()
            self.assertEqual(state["termination"], termination)
            self.assertEqual(state["result"], result)
            self.assertEqual(state["legal_moves"], [])
            with self.assertRaises(GuiError):
                self.action("engine")
        self.session.board = chess.Board("7k/8/5KQ1/8/8/8/8/8 w - - 0 1")
        self.action("move", move="g6g7")
        self.assertEqual(self.session.state()["termination"], "CHECKMATE")
        self.assertIn('[Result "1-0"]', self.session.pgn())
        self.action("undo")
        self.assertEqual(self.session.state()["result"], "*")

    def test_repetition_history_is_preserved(self):
        self.session.board = chess.Board()
        for move in ["g1f3", "g8f6", "f3g1", "f6g8"] * 2:
            self.session.board.push_uci(move)
        self.assertEqual(self.session.state()["termination"], "THREEFOLD_REPETITION")
        self.assertEqual(chess.pgn.read_game(io.StringIO(self.session.pgn())).headers["Result"], "1/2-1/2")
        self.action("undo")
        self.assertFalse(self.session.board.can_claim_threefold_repetition())

    def test_invalid_settings_preserve_game(self):
        before = self.session.state()
        for config in ({"color": "red"}, {"evaluator": "NNUE"}, {"seconds": True},
                       {"seconds": float("nan")}, {"seconds": 0}, {"seconds": 11},
                       {"seconds": 10 ** 400}, {"evaluator": "Linear"},
                       {"model": "x\nquit"}, {"model": []}):
            with self.assertRaises(GuiError):
                self.action("new", **config)
            self.assertEqual(self.session.state(), before)
        with tempfile.TemporaryDirectory() as temp:
            model = Path(temp) / "invalid model.txt"
            model.write_text("not a model")
            with self.assertRaises(GuiError):
                self.action("new", evaluator="Linear", model=str(model))
            self.assertEqual(self.session.state(), before)
        self.action("move", move="e2e4")
        self.action("engine")  # Old engine is still usable after failed replacement.

    def test_linear_v1_and_v2_identity_and_real_play(self):
        for path in ("experiments/results/r3-model-v1/model.txt", "experiments/results/r4-models-v1/full.txt"):
            with tempfile.TemporaryDirectory(prefix="ucl model ") as temp:
                model = Path(temp) / "model with spaces.txt"
                model.write_bytes((ROOT / path).read_bytes())
                state = self.action("new", evaluator="Linear", model=str(model), seconds=0.01)
                self.assertTrue(state["identity"]["evaluator"].startswith("linear-v"))
                self.assertEqual(state["identity"]["model_sha256"], hashlib.sha256(model.read_bytes()).hexdigest())
                self.action("move", move="e2e4")
                self.assertEqual(len(self.action("engine")["moves"]), 2)
                self.assertIn(state["identity"]["model_sha256"], self.session.pgn())

    def test_engine_failure_does_not_push_and_retry_restarts(self):
        self.action("move", move="e2e4")
        before = self.session.state()
        self.session.engine.close()
        with self.assertRaises(GuiError) as raised:
            self.action("engine")
        self.assertEqual(raised.exception.status, 503)
        self.assertEqual(before, self.session.state())
        self.assertEqual(len(self.action("engine")["moves"]), 2)

    def test_complete_game_from_start_through_http(self):
        server = GuiServer(("127.0.0.1", 0), self.session)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        helper = chess.engine.SimpleEngine.popen_uci(str(ENGINE), timeout=5)
        self.addCleanup(close_engine, helper)
        url = f"http://127.0.0.1:{server.server_port}"
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        def get(path):
            with opener.open(url + path, timeout=15) as response:
                return response.read()
        def post(action, state, **data):
            request = urllib.request.Request(url + "/api/" + action,
                json.dumps({"revision": state["revision"], **data}).encode(), {"Content-Type": "application/json"})
            with opener.open(request, timeout=15) as response:
                return json.load(response)
        state = json.loads(get("/api/state"))
        replay = chess.Board()
        for _ in range(800):
            if state["result"] != "*":
                break
            if state["engine_turn"]:
                state = post("engine", state)
            else:
                move = helper.play(replay, chess.engine.Limit(depth=2)).move
                state = post("move", state, move=move.uci())
            replay.push_uci(state["moves"][-1]["uci"])
            self.assertEqual(replay.fen(), state["fen"])
        self.assertNotEqual(state["result"], "*", "Game must end naturally, no move cap adjudication")
        raw = get("/api/pgn").decode()
        game = chess.pgn.read_game(io.StringIO(raw))
        self.assertEqual(game.errors, [])
        self.assertEqual(game.end().board().fen(), replay.fen())
        self.assertEqual(game.headers["Result"], replay.outcome(claim_draw=True).result())
        print(f"\nGUI HTTP full game: {len(state['moves'])} plies, {state['result']}, {state['termination']}")
        if os.environ.get("UCL_GUI_EVIDENCE"):
            Path(os.environ["UCL_GUI_EVIDENCE"]).write_text(raw, encoding="utf-8")


@unittest.skipUnless(ENGINE.is_file(), "Build UCL or set UCL_ENGINE")
class HttpTests(unittest.TestCase):
    def setUp(self):
        self.session = GameSession(ENGINE, seconds=0.01)
        self.server = GuiServer(("127.0.0.1", 0), self.session)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.session.close)
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.url = f"http://127.0.0.1:{self.server.server_port}"
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def request(self, path, data=None, headers=None):
        request = urllib.request.Request(self.url + path, data, headers or {})
        try:
            return self.opener.open(request, timeout=10)
        except urllib.error.HTTPError as response:
            return response

    def post(self, path, **data):
        return self.request(path, json.dumps({"revision": self.session.revision, **data}).encode(),
                            {"Content-Type": "application/json"})

    def test_assets_and_local_request_guards(self):
        for path, mime in (("/", "text/html"), ("/app.js", "text/javascript"),
                           ("/style.css", "text/css"),
                           ("/vendor/cm-chessboard/src/Chessboard.js", "text/javascript"),
                           ("/vendor/cm-chessboard/assets/pieces/standard.svg", "image/svg+xml")):
            with self.request(path) as response:
                self.assertEqual(response.status, 200, path)
                self.assertEqual(response.headers.get_content_type(), mime)
                self.assertTrue(response.read())
        for path in ("/../gui.py", "/missing", "/api/unknown"):
            with self.request(path) as response:
                self.assertEqual(response.status, 404)
        with self.request("/api/state", headers={"Host": "evil.example"}) as response:
            self.assertEqual(response.status, 403)
        with self.request("/api/new", b'{}', {"Content-Type": "application/json", "Origin": "https://evil.example"}) as response:
            self.assertEqual(response.status, 403)
        with self.request("/api/new", b'{}', {"Content-Type": "text/plain"}) as response:
            self.assertEqual(response.status, 415)
        for raw in (b'[1]', b'{', b'NaN', b'x' * 16385):
            with self.request("/api/new", raw, {"Content-Type": "application/json"}) as response:
                self.assertIn(response.status, (400, 413))
        self.assertEqual(self.session.board.fen(), chess.STARTING_FEN)

    def test_http_illegal_stale_promotion_and_undo(self):
        before = self.session.state()
        with self.post("/api/move", move="e2e5") as response:
            self.assertEqual(response.status, 400)
            self.assertEqual(json.load(response)["state"], before)
        self.session.board = chess.Board("7k/P7/8/8/8/8/8/7K w - - 0 1")
        with self.post("/api/move", move="a7a8n") as response:
            self.assertEqual(response.status, 200)
            self.assertEqual(json.load(response)["termination"], "INSUFFICIENT_MATERIAL")
        with self.post("/api/undo") as response:
            self.assertEqual(response.status, 200)
            self.assertEqual(json.load(response)["turn"], "white")
        raw = json.dumps({"revision": before["revision"], "move": "a7a8q"}).encode()
        with self.request("/api/move", raw, {"Content-Type": "application/json"}) as response:
            self.assertEqual(response.status, 409)


if __name__ == "__main__":
    unittest.main()

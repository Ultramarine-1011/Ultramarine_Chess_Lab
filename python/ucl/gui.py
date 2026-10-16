"""Single-user, loopback-only chess GUI: python -m ucl.gui."""
from __future__ import annotations

import argparse
import asyncio
import concurrent.futures
import hashlib
import json
import math
import os
import mimetypes
import threading
import webbrowser
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

import chess
import chess.engine
import chess.pgn

WEB_ROOT = Path(__file__).with_name("web")


class GuiError(ValueError):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


class IdentityCommand(chess.engine.BaseCommand):
    """Read UCL's existing evalinfo extension, fenced by isready."""
    def start(self):
        self.identity = None
        self._engine.send_line("evalinfo")
        self._engine.send_line("isready")

    def line_received(self, line):
        prefix = "info string ucl_evaluator "
        if line.startswith(prefix):
            try:
                self.identity = json.loads(line[len(prefix):])
            except ValueError as exc:
                raise chess.engine.EngineError("Invalid UCL evalinfo") from exc
        elif line == "readyok":
            self.result.set_result(self.identity)
            self.set_finished()


def engine_identity(engine):
    async def query():
        return await asyncio.wait_for(engine.protocol.communicate(IdentityCommand), 5)
    return asyncio.run_coroutine_threadsafe(query(), engine.protocol.loop).result(timeout=6)


def close_engine(engine):
    if engine is not None:
        try:
            engine.quit()
        except (chess.engine.EngineError, TimeoutError, concurrent.futures.CancelledError):
            pass
        finally:
            engine.close()


class GameSession:
    """One authoritative python-chess board and one UCI child, serialized by lock."""
    def __init__(self, engine_path: Path, *, color="white", seconds=0.25,
                 evaluator="Handcrafted", model="", model_root=None):
        self.engine_path = Path(engine_path).resolve()
        self.model_root = Path(model_root or Path.cwd()).resolve()
        self.lock = threading.RLock()
        self.engine = None
        self.revision = 0
        self.new_game({"color": color, "seconds": seconds, "evaluator": evaluator, "model": model})

    def open_engine(self, config):
        candidate = chess.engine.SimpleEngine.popen_uci(str(self.engine_path), timeout=5)
        try:
            options = {"Evaluator": config["evaluator"]}
            expected_hash = None
            if config["evaluator"] == "Linear":
                path = Path(config["model"])
                if not path.is_absolute():
                    path = self.model_root / path
                path = path.resolve(strict=True)
                if not path.is_file() or path.stat().st_size > 4096:
                    raise GuiError("模型必须是最多 4096 字节的 UCL Linear 文件。")
                expected_hash = hashlib.sha256(path.read_bytes()).hexdigest()
                # UCI option ordering is significant; loading is validated by the engine.
                candidate.configure({"ModelSHA256": expected_hash, "ModelFile": str(path)})
            candidate.configure(options)
            identity = engine_identity(candidate)
            expected_names = {"handcrafted-v1"} if expected_hash is None else {"linear-v1", "linear-v2"}
            if (not isinstance(identity, dict) or identity.get("evaluator") not in expected_names
                    or identity.get("model_sha256") != expected_hash):
                raise GuiError("引擎未接受评估器或模型；请检查 UCL 模型格式。")
            return candidate, identity
        except BaseException:
            close_engine(candidate)
            raise

    @staticmethod
    def validate_config(data):
        color = data.get("color", "white")
        evaluator = data.get("evaluator", "Handcrafted")
        seconds = data.get("seconds", 0.25)
        model = data.get("model", "")
        if color not in ("white", "black") or evaluator not in ("Handcrafted", "Linear"):
            raise GuiError("无效的执棋颜色或评估器。")
        if type(seconds) not in (float, int) or not 0.01 <= seconds <= 10 or not math.isfinite(seconds):
            raise GuiError("每步思考时间须为 0.01–10 秒。")
        if not isinstance(model, str) or len(model) > 2048 or any(c in model for c in "\r\n\0"):
            raise GuiError("无效的模型路径。")
        if evaluator == "Linear" and not model.strip():
            raise GuiError("Linear 需要本地模型路径。")
        return {"color": color, "evaluator": evaluator, "seconds": float(seconds), "model": model}

    def new_game(self, data):
        with self.lock:
            config = self.validate_config(data)
            candidate, identity = self.open_engine(config)
            previous = self.engine
            self.engine, self.identity, self.config = candidate, identity, config
            self.board = chess.Board()
            self.game_id = object()
            self.started = date.today().strftime("%Y.%m.%d")
            self.revision += 1
            close_engine(previous)
            return self.state()

    @property
    def human(self):
        return self.config["color"] == "white"

    def outcome(self):
        # Claim available draws automatically, including a claim via the next move.
        return self.board.outcome(claim_draw=True)

    def state(self):
        with self.lock:
            outcome = self.outcome()
            replay = self.board.root()
            moves = []
            for move in self.board.move_stack:
                moves.append({"uci": move.uci(), "san": replay.san(move),
                              "number": replay.fullmove_number, "color": "white" if replay.turn else "black"})
                replay.push(move)
            return {"revision": self.revision, "fen": self.board.fen(), "config": self.config,
                    "identity": self.identity, "turn": "white" if self.board.turn else "black",
                    "check": self.board.is_check(), "moves": moves,
                    "legal_moves": [m.uci() for m in self.board.legal_moves] if outcome is None else [],
                    "engine_turn": outcome is None and self.board.turn != self.human,
                    "can_undo": len(moves) > (0 if self.human else 1),
                    "result": outcome.result() if outcome else "*",
                    "termination": outcome.termination.name if outcome else None}

    def check_revision(self, data):
        if type(data.get("revision")) is not int or data["revision"] != self.revision:
            raise GuiError("棋局已更新，请按当前局面操作。", 409)

    def action(self, action, data):
        with self.lock:
            self.check_revision(data)
            if action == "new":
                return self.new_game(data)
            if action == "undo":
                if not self.state()["can_undo"]:
                    raise GuiError("还没有可悔的己方着法。")
                self.board.pop()
                while self.board.move_stack and self.board.turn != self.human:
                    self.board.pop()
            elif action == "move":
                if self.outcome() or self.board.turn != self.human:
                    raise GuiError("现在不是你的回合，或棋局已结束。")
                uci = data.get("move")
                if not isinstance(uci, str):
                    raise GuiError("请提交 UCI 着法，例如 e2e4。")
                try:
                    move = chess.Move.from_uci(uci)
                except ValueError as exc:
                    raise GuiError("无效的着法格式。") from exc
                if move not in self.board.legal_moves:
                    raise GuiError("非法着法；升变时请选择后、车、象或马。")
                self.board.push(move)
            elif action == "engine":
                if self.outcome() or self.board.turn == self.human:
                    raise GuiError("当前无需引擎落子。")
                try:
                    if self.engine is None:
                        self.engine, self.identity = self.open_engine(self.config)
                    result = self.engine.play(self.board, chess.engine.Limit(time=self.config["seconds"]),
                                              game=self.game_id)
                    if result.move is None or result.move not in self.board.legal_moves:
                        raise chess.engine.EngineError("引擎未返回合法着法")
                    self.board.push(result.move)
                except (chess.engine.EngineError, OSError, TimeoutError) as exc:
                    close_engine(self.engine)
                    self.engine = None
                    raise GuiError(f"引擎应答失败，可重试或悔棋：{exc}", 503) from exc
            else:
                raise GuiError("未知操作。", 404)
            self.revision += 1
            return self.state()

    def pgn(self):
        with self.lock:
            game = chess.pgn.Game.from_board(self.board)
            game.headers.update({"Event": "UCL local game", "Site": "Local", "Date": self.started,
                                 "White": "Human" if self.human else "UCL",
                                 "Black": "UCL" if self.human else "Human",
                                 "Result": self.state()["result"],
                                 "Evaluator": self.identity["evaluator"],
                                 "TimeControl": "?", "UCLMoveTime": str(self.config["seconds"])})
            if self.identity.get("model_sha256"):
                game.headers["ModelSHA256"] = self.identity["model_sha256"]
            if self.outcome():
                game.headers["Termination"] = self.outcome().termination.name.lower()
            return str(game) + "\n"

    def close(self):
        with self.lock:
            close_engine(self.engine)
            self.engine = None


class GuiServer(ThreadingHTTPServer):
    daemon_threads = True
    block_on_close = False

    def __init__(self, address, session):
        self.session = session
        super().__init__(address, GuiHandler)


class GuiHandler(BaseHTTPRequestHandler):
    server: GuiServer

    def log_message(self, format, *args):
        pass

    def send(self, status, body, content_type):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
        self.end_headers()
        self.wfile.write(body)

    def json_response(self, status, value):
        self.send(status, json.dumps(value, ensure_ascii=False).encode(), "application/json; charset=utf-8")

    def check_local(self):
        port = self.server.server_port
        hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
        if self.headers.get("Host") not in hosts:
            raise GuiError("仅接受本机地址。", 403)
        origin = self.headers.get("Origin")
        if origin is not None and origin not in {f"http://{host}" for host in hosts}:
            raise GuiError("拒绝跨站请求。", 403)

    def do_GET(self):
        try:
            self.check_local()
            path = urlsplit(self.path).path
            if path == "/api/state":
                return self.json_response(200, self.server.session.state())
            if path == "/api/pgn":
                self.send_response(200)
                body = self.server.session.pgn().encode()
                self.send_header("Content-Type", "application/x-chess-pgn; charset=utf-8")
                self.send_header("Content-Disposition", 'attachment; filename="ucl-game.pgn"')
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)
                return
            file = (WEB_ROOT / ("index.html" if path == "/" else path.lstrip("/"))).resolve()
            if not file.is_relative_to(WEB_ROOT.resolve()) or not file.is_file():
                raise GuiError("未找到页面。", 404)
            mime = mimetypes.guess_type(file)[0] or "application/octet-stream"
            if file.suffix == ".js":
                mime = "text/javascript"
            self.send(200, file.read_bytes(), mime)
        except GuiError as exc:
            self.json_response(exc.status, {"error": str(exc)})

    def do_POST(self):
        try:
            self.check_local()
            if self.headers.get_content_type() != "application/json":
                raise GuiError("需要 application/json。", 415)
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError as exc:
                raise GuiError("无效的请求长度。") from exc
            if not 0 < length <= 16384:
                raise GuiError("请求过大或为空。", 413)
            try:
                data = json.loads(self.rfile.read(length))
            except (ValueError, UnicodeDecodeError) as exc:
                raise GuiError("无效的 JSON。") from exc
            if not isinstance(data, dict):
                raise GuiError("请求必须是 JSON 对象。")
            path = urlsplit(self.path).path
            if path not in {"/api/new", "/api/move", "/api/engine", "/api/undo"}:
                raise GuiError("未知操作。", 404)
            self.json_response(200, self.server.session.action(path.rsplit("/", 1)[1], data))
        except (GuiError, chess.engine.EngineError, OSError, TimeoutError) as exc:
            self.json_response(exc.status if isinstance(exc, GuiError) else 400,
                               {"error": str(exc), "state": self.server.session.state()})


def main(argv=None):
    parser = argparse.ArgumentParser(description="UCL 本地人机对弈（仅监听 127.0.0.1）")
    parser.add_argument("--engine", type=Path, help="UCL 可执行文件；默认 build/release/ucl[.exe]")
    parser.add_argument("--port", type=int, default=8765, help="本地端口，0 表示自动选择")
    parser.add_argument("--color", choices=("white", "black"), default="white")
    parser.add_argument("--seconds", type=float, default=0.25)
    parser.add_argument("--evaluator", choices=("Handcrafted", "Linear"), default="Handcrafted")
    parser.add_argument("--model", default="", help="Linear 模型路径（相对启动目录或绝对路径）")
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args(argv)
    engine_path = args.engine or Path("build/release/ucl.exe" if os.name == "nt" else "build/release/ucl")
    if not engine_path.is_file():
        parser.error(f"未找到引擎 {engine_path}；请先 cmake --preset release 并构建，或使用 --engine。")
    if not 0 <= args.port <= 65535:
        parser.error("端口须在 0–65535 范围内。")
    session = None
    server = None
    try:
        session = GameSession(engine_path, color=args.color, seconds=args.seconds,
                              evaluator=args.evaluator, model=args.model)
        server = GuiServer(("127.0.0.1", args.port), session)
        url = f"http://127.0.0.1:{server.server_port}"
        print(f"UCL 本地对弈：{url}  （Ctrl+C 退出）", flush=True)
        if not args.no_browser:
            webbrowser.open(url)
        server.serve_forever(poll_interval=0.2)
    except KeyboardInterrupt:
        pass
    except (GuiError, chess.engine.EngineError, OSError, TimeoutError) as exc:
        parser.exit(1, f"无法启动本地对弈：{exc}\n")
    finally:
        if server:
            server.server_close()
        if session:
            session.close()


if __name__ == "__main__":
    main()

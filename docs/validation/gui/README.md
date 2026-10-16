# Local GUI validation — 2026-10-16

Base: `eff1a6e38ffd9cdb324e1637ad773949f22b4a75` (latest main), plus dirty GUI changes
in the delivery commit. Independent shallow/partial clone in `UCL_GUI_Local`;
sparse checkout includes source/docs, all required regression fixtures and the v1/v2
models. Large historical research logs were not downloaded or changed.
Host: macOS arm64, AppleClang, CMake 4.4.4/Ninja 1.13.2, Python 3.14.5,
python-chess 1.11.2; browser Chrome for Testing 149 via agent-browser 0.27.0.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
.venv/bin/python -m pip install --no-deps -e .
cmake --preset release -DPython3_EXECUTABLE="$PWD/.venv/bin/python"
cmake --build --preset release --parallel 4
ctest --preset release -R '^gui$' --output-on-failure
.venv/bin/python -m unittest discover -s tests -p test_gui.py -v
ctest --preset release --output-on-failure
.venv/bin/python -m pip check
.venv/bin/python -m pip wheel --no-deps . -w .tools/gui-validation/wheels
.venv/bin/python -m ucl.gui --no-browser
```

| Check | Result |
|---|---|
| Release configure/build | PASS |
| GUI, real UCL executable | 13 tests PASS; 1.785 s in the verbose run |
| Full Release CTest | 7/7 PASS, 13.51 s |
| HTTP full game | 37 legal plies from startpos, natural checkmate, 1–0; no external adjudication |
| Actual browser full game | Same 37 plies entered through page move form; displayed victory/checkmate; downloaded PGN independently replayed |
| Click board, illegal keyboard move, undo | PASS; real engine response, illegal move leaves board/history unchanged |
| Promotions | White Q/N/R/B and black N, missing suffix rejected; browser Knight dialog, draw, undo and Escape cancellation PASS |
| Special/terminal rules | Castling, en passant, mate/stalemate, material, fifty-move, repetition, undo after terminal PASS |
| Evaluator | Real v1/v2 loading/identity/hash/play PASS; paths with spaces; failed replacement preserves old game/engine |
| Failure/retry and revision | Dead engine does not push a move; retry respawns; stale mutation rejected |
| HTTP boundary | Host/Origin, JSON shape/size/type, static traversal PASS |
| Packaging | Wheel contains all 20 local web files; all vendored module imports resolve; pip check PASS |
| Browser layout | 320/768/1024 px widths equal document width, no horizontal overflow; 1440 px desktop visually inspected |
| Browser diagnostics | No JS errors or console errors |

The complete [downloaded browser PGN](full-game.pgn) retains actual engine settings
and result. Its White "Human" moves were automated for acceptance using a second
real UCL at depth 2; Black is the GUI's real UCL at 0.01 seconds/move. This is an
interface/rules test, not a playing-strength experiment. At 0.01 seconds the existing
10 ms MoveOverhead can select the engine's legal zero-depth fallback; ordinary
manual play was also checked at 0.25 seconds. No search/evaluator code changed.

Initial local failures: Host rejection test traversed the environment HTTP proxy
(502); test clients now explicitly bypass proxies for loopback only. The first
full suite lacked the sparse clone's archived r3-data-v1 fixture; the original
fixture was fetched and all tests rerun. Neither failure required engine/research
changes. GUI responses/errors were not weakened.

Local Debug/sanitizer and Windows physical-host checks were not run for this
Python/static-only change. Hosted macOS/Windows CI status is recorded below after push.

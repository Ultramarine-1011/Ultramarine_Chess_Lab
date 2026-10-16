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

## Clean delivery checks

Code commit `f3f40407b9b66cff877536f82e2c14e5244118d1` was pushed to
`codex/local-chess-gui`. Reconfigured and rebuilt from clean source (`--build-info`
reports dirty=false): [Release 7/7](release.log), 15.15 s, and [Debug 7/7](debug.log),
42.39 s. Debug used the same configure/build/ctest commands above with preset `debug`.
[ASan/UBSan 7/7](sanitize.log), 96.70 s, with no sanitizer diagnostics. Sanitizer used preset `sanitize`. CLI with `--port 0 --no-browser`
served `/api/state`, then handled SIGINT/Ctrl+C, exited 0 and closed its engine.
The final wheel rebuilt successfully. `git diff --check` passes except the exact
vendored `standard.svg` LICENSE underline (`=======`), which Git mistakes for a
conflict marker; all 17 vendored files are byte-identical to the verified archive.

[GitHub Actions run 38905365257](https://github.com/Ultramarine-1011/Ultramarine_Chess_Lab/actions/runs/38905365257)
failed **before any job steps started**. GitHub reports: “The job was not started
because recent account payments have failed or your spending limit needs to be
increased.” The [saved response](ci.json) records all five empty-step jobs and
annotations. This is an external account/billing blocker; no hosted macOS/Windows
code/tests ran, and the failure cannot be repaired by changing GUI code. No workflow
or billing settings were changed and no identical reruns were triggered.
Windows physical-host GUI checks were not run. Local checks do not establish a
Windows result; earlier main's successful CI remains historical evidence only.

## Final browser race regression

Final review found the initial renderer could lose a board flip when a fast new
game completed before cm-chessboard's queued `setOrientation`. The displayed
player/turn was correct but the board could remain White-oriented. The renderer
now constructs the new game's board directly in the requested orientation; it
never queues redundant flips. Python/C++ are unchanged from the clean f3f4040 tests.

Tested `f3f4040` + dirty `web/app.js` fix and [browser regression](browser-check.js):

```sh
agent-browser --session ucl-gui open http://127.0.0.1:8765
agent-browser --session ucl-gui eval --stdin < docs/validation/gui/browser-check.js
agent-browser --session ucl-gui errors
agent-browser --session ucl-gui console
node --input-type=module --check < python/ucl/web/app.js
ctest --preset release --output-on-failure
```

Six alternating White/Black new games at 0.01 s PASS with actual SVG square
coordinates asserted, followed by the full 37-ply checkmate through the move form
and undo from terminal PASS. No browser errors/console messages. The final Release
run also passes 7/7. This regression is retained as a small browser script without
adding a browser/runtime build dependency.

# R6 reproduction and execution evidence

Run from the repository root, Windows PowerShell. Reuse `.tools/windows-env.ps1`,
the existing venv, MSVC prefix fix and pinned fastchess. All Python commands use
`python -X utf8` (`.venv/Scripts/python.exe` below). New outputs must use separate
directories; do not overwrite the archived independent test or formal matches.

For a fresh host, use an installed VS Developer PowerShell and the venv from
README.md; `.tools/windows-env.ps1` is a local convenience helper. The recorded
local `.tools/windows-msvc-rules.cmake` is byte-identical to the committed
`docs/validation/windows-init-20261015/windows-msvc-rules.cmake`. The following
optional acquisition commands apply to a fresh tools directory; the actual R6
run reused its already verified fastchess and downloaded Stockfish once.

```powershell
New-Item -ItemType Directory -Force .tools/r6-stockfish,.tools/bin | Out-Null
curl.exe -L --connect-timeout 20 --max-time 600 -o .tools/r6-stockfish/stockfish.zip https://github.com/official-stockfish/Stockfish/releases/download/sf_17.1/stockfish-windows-x86-64-avx2.zip
if ((Get-FileHash .tools/r6-stockfish/stockfish.zip).Hash -ne '92a77f8d8116b4331696eeb7b232bd03db30d6641a6ce1be1759478b8931d28b') { throw 'Stockfish ZIP identity mismatch' }
Expand-Archive .tools/r6-stockfish/stockfish.zip .tools/r6-stockfish/unpacked
curl.exe -L --connect-timeout 20 --max-time 600 -o .tools/fastchess-1.8.2.zip https://github.com/Disservin/fastchess/releases/download/v1.8.2-alpha/fastchess-windows-x86-64.zip
Expand-Archive .tools/fastchess-1.8.2.zip .tools/fastchess-v1.8.2-alpha
$r6Fastchess = '.tools/fastchess-v1.8.2-alpha/fastchess-windows-x86-64/fastchess.exe'
if ((Get-FileHash $r6Fastchess).Hash -ne 'c6d7e4458a58025983c81bf38c524cb213e6f27559657dcfd72543392a431a71') { throw 'fastchess identity mismatch' }
Copy-Item $r6Fastchess .tools/bin/fastchess.exe
```

The general `bootstrap_fastchess.py` pins the older research/CI tool; it does
not supply the v1.8.2-alpha executable used in these Windows formal matches.

```powershell
. .tools/windows-env.ps1
python -X utf8 -m ucl.r6_data acquire --output experiments/results/r6-data-v1
python -X utf8 -m ucl.r6_data validate --output experiments/results/r6-data-v1
python -X utf8 -m ucl.r6_data features --input experiments/results/r6-data-v1 --engine build/release/ucl.exe --output experiments/results/r6-features-v1
# SF is the official sf_17.1 Windows AVX2 binary; acquisition/hash in teacher-release.json.
$r6Teacher = '.tools/r6-stockfish/unpacked/stockfish/stockfish-windows-x86-64-avx2.exe'
python -X utf8 -m ucl.r6_data preflight --input experiments/results/r6-features-v1/features.jsonl.gz --engine $r6Teacher --output experiments/results/r6-preflight-v1
python -X utf8 -m ucl.r6_data label --input experiments/results/r6-features-v1/features.jsonl.gz --engine $r6Teacher --output experiments/results/r6-labels-v1
python -X utf8 -m ucl.r6_data rank --input experiments/results/r6-features-v1/features.jsonl.gz --split validation --engine $r6Teacher --output experiments/results/r6-ranking-validation-v1
python -X utf8 -m ucl.r6_training fit --input experiments/results/r6-labels-v1/labels.jsonl.gz --rank experiments/results/r6-ranking-validation-v1/children.jsonl.gz --output experiments/results/r6-models-v1
python -X utf8 -m ucl.r6_training verify --output experiments/results/r6-models-v1
# Refit to .tools/r6-refit produced all four identical model files (refit.json).
$r6Python = (Resolve-Path .venv/Scripts/python.exe).Path
$r6MsvcFix = (Resolve-Path docs/validation/windows-init-20261015/windows-msvc-rules.cmake).Path
cmake --preset release "-DPython3_EXECUTABLE=$r6Python" "-DCMAKE_PROJECT_INCLUDE=$r6MsvcFix"
cmake --build --preset release --parallel 4
ctest --preset release
# Copy this clean binary to ignored .tools/r6-engine/ucl.exe before later commits.
python -X utf8 -m ucl.r6_study configure --engine .tools/r6-engine/ucl.exe --output experiments/configs/r6
# Commit model selection, analysis code and freeze/configs before the next commands.
python -X utf8 -m ucl.r6_data rank --input experiments/results/r6-features-v1/features.jsonl.gz --split test --engine $r6Teacher --output experiments/results/r6-ranking-test-v1
python -X utf8 -m ucl.r6_training test --rank experiments/results/r6-ranking-test-v1/children.jsonl.gz --output experiments/results/r6-models-v1
python -X utf8 -m ucl.r6_study matches --output experiments/results/r6-matches-v1
python -X utf8 -m ucl.r6_study analyze --input experiments/results/r6-matches-v1 --output experiments/results/r6-analysis-v1
python -X utf8 docs/r6/generate-report.py
```

Offline dataset reconstruction uses the saved five selected PGNs. New network
acquisition requires exactly the registered bounded prefixes; large `.zst` and
teacher binaries are ignored. Completed label files can be read without repeat
queries; partial work uses an ignored append journal. Use another directory to
rebuild labels from scratch. Ranking child records retain their own queried
scores; root scores are never substituted. Teacher output selects the last exact
iteration, excluding aspiration bounds; actual final nodes are retained too.

To check model reproducibility, fit into a fresh directory such as
`.tools/r6-replica-models`, then compare its four model hashes with the archived
files. A new independent replication may rebuild the clean engine with
`python -X utf8 scripts/build_revision.py 0403a9dbf0f4104593990467720c9116b2f014fe`.
If that binary has a different build hash, create a new freeze rather than edit
the archived freeze: configure with `--study .tools/r6-replica-models`, the rebuilt
`--engine`, and `--output .tools/r6-replica-configs`; run matches with that same
`--study`, `--input .tools/r6-replica-configs` and a new output directory. This is
a replication on already known data/openings, not a new independent sample;
do not merge it into the R6 fixed 1600 games.

The preregistered cost suite is R2. To also cover the requested common validation
positions, an exploratory supplement was measured after all matches, using the
first ten of the registered validation-root hash order. The committed
`experiments/positions/r6-validation-v1.json` stores FENs/source identities and
the input hash. Its identity was checked against the original validation rows.
Run the four `experiments/configs/r6/validation-*.json` configurations through
`ucl-lab benchmark --config <config> --output <new-directory>` to repeat this
measurement with the retained binary; a rebuilt binary needs copied configs with
its own path/identity. Raw outputs are in `r6-validation-performance-v1`.
This supplement and the reported paired C−D interval are explicitly post hoc
exploratory diagnostics. Neither changed model selection or any formal game.

During formal execution, the CLI was corrected to pass --study to this freeze
lookup for new replication directories. The live coordinator was not restarted;
its engine, models, budgets, openings and analysis were unchanged. A separate
checksum-guard check confirmed rejection before creating output or starting games.

Preflight: 256 real training positions, 139 white/117 black to move; eight cold
queries exact on repetition. Three pilot fits/deployments passed. Final 23998
features match independent Python exactly. All four final models reproduce byte
for byte; 95992 deployment queries match rounded cp exactly (raw error <1e-9).
Dataset and openings reconstruct exactly: 3601 games/23998 positions/200 openings.
Release CTest6/6, including new perspective/mate/terminal/black-root checks.

Operational deviations before freeze: an initial PowerShell binary transfer was
interrupted and curl resumed the official asset; ZIP/executable hashes retained.
Validation ranking briefly overlapped main labeling (up to eight workers rather
than four); that ranking process was stopped and resumed only after main labeling
completed. Its 2496 completed child records were preserved. Query node budget,
cold hash, labels and subsequent model selection were unchanged. No timing or
strength inference uses labeling elapsed time. A release-metadata read initially
hit the Windows GBK default; explicit UTF-8 fixed it. Saved native logs retain
CRLF bytes; source and generated research JSON/model files use LF.

The teacher's own NNUE is an external fixed label source. No NNUE/RL/MCTS or new
search algorithm was implemented in UCL. Archive data directories intentionally
omit disposable duplicate plain-text journals.

## Completed execution

| Check | Actual outcome | Evidence |
|---|---|---|
| Data/opening reconstruction | exit0, 3601 games/23998 positions/200 openings | r6-reconstruct.log; dataset manifest |
| Features and deployment | all23998 C++/Python features exact; 95992 rounded scores exact | r6-deployment.log; verification.json |
| Fit/re-fit | all20 candidates converged; four model files byte-identical | fits.json; refit.json |
| Independent test | exit0, once after1ca065a freeze; candidate unchanged | r6-test.log; test-results.json |
| Registered and supplemental costs | exit0, all records completed | r6-performance.log; r6-validation-performance.log |
| Formal A/B/C/D | exit0, each400/200 pairs, total1600 | r6-matches.log; raw record/PGN/UCI bundles |
| Full match analysis | exit0, every PGN move/PV/history matches UCI, abnormal0 | r6-analysis.log; r6-analysis-v1 |
| Node condition D | actual go/counters/clock verified; 1703 mate + 7 max-depth undershoots | D/analysis.json; moves.jsonl.gz |
| Frozen identity audit | dataset/model/config/binary/tool/opening hashes agree | final-input-checks.json; final-match-checks.json |
| Report | links valid, deterministic generation, numerical tables read from actual JSON | report-checks.json |
| Windows Release | configure/build/CTest exit0, 6/6 | r6-configure.log; r6-build.log; r6-final-ctest.log |
| Cross-platform code CI | five successful jobs at3524319 | ci-code.json; link below |

[Code CI run](https://github.com/Ultramarine-1011/Ultramarine_Chess_Lab/actions/runs/38893285837)
covers Windows/macOS Release/Debug and sanitizer. The earlier bb75a56 snapshot is
also retained in ci.json. Final results/report delivery is recorded in VALIDATION.md.
One normal push encountered a Schannel handshake failure; a per-command OpenSSL
backend retry succeeded. No global Git/system configuration changed.

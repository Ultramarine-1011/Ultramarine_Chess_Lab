# R6 reproduction and execution evidence

Run from the repository root, Windows PowerShell. Reuse `.tools/windows-env.ps1`,
the existing venv, MSVC prefix fix and pinned fastchess. All Python commands use
`python -X utf8` (`.venv/Scripts/python.exe` below). New outputs must use separate
directories; do not overwrite the archived independent test or formal matches.

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
cmake --preset release -DPython3_EXECUTABLE=C:/Ultramarine_Chess_Lab/Ultramarine_Chess_Lab/.venv/Scripts/python.exe -DCMAKE_PROJECT_INCLUDE=C:/Ultramarine_Chess_Lab/Ultramarine_Chess_Lab/.tools/windows-msvc-rules.cmake
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

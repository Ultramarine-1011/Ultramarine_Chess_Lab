# Daily Elo entry validation (2026-10-17)

Scope: lightweight daily workspace/baseline comparison, documentation, tests,
commit and ordinary push. No new research stage, framework or CI match.

The initial clean local checkout was `80616335bdd1455201c13562ced8673d7da9b99f`.
Fetched and integrated current main `eff1a6e38ffd9cdb324e1637ad773949f22b4a75`
before final validation, preserving the R5/R6 interfaces and historical evidence.
The host proxy and an interrupted Git pack transfer delayed synchronization;
all missing Git objects were recovered through the authenticated GitHub API and
verified by their Git object hashes. Temporary fetch settings were removed.
An initial new test incorrectly compared open log handles across builds;
corrected it to compare subprocess argument arrays. No production fix was needed.

## Local commands and results

All final checks used main `eff1a6e38ffd9cdb324e1637ad773949f22b4a75` plus
this task's dirty Python/docs/opening changes. No C++ engine source changed.
Host/toolchain, binary hashes and actual build-info are in `verification.json`.

```sh
.venv/bin/python scripts/elo.py --set-baseline HEAD
.venv/bin/python scripts/elo.py --games 8
PYTHONPATH=python .venv/bin/python -m unittest discover -s tests -p test_experiments.py
cmake --preset release -DPython3_EXECUTABLE="$PWD/.venv/bin/python"
cmake --build --preset release --parallel 4
ctest --preset release -R '^experiments$'
ctest --preset release
```

- Baseline: isolated clean Release build of `eff1a6e`; saved SHA remains fixed.
- Real 8-game match: PASS, default 2+0.02 / concurrency4, 4 distinct openings with
  swapped colors, no depth/nodes limits. 5W/0D/3L, score62.5%, paired score95%
  [50%,87.5%], logistic relative Elo+88.7395 [0,338.0392]. See `e2e.log`.
- Bundle integrity/recomputed statistics: PASS. Independent PGN header counts
  and actual first-four EPD positions/color coverage also match retained results.
- Cache: calling `elo.baseline_binary(saved_sha)` repeatedly leaves binary SHA
  and mtime unchanged. Repeating `elo.build_candidate()` reports Ninja
  `no work to do`; dirty=true and Release metadata remain accurate.
- Targeted: PASS, 21 tests; parameter boundaries, SHA/cache integrity, dirty
  incremental build, default config, Elo boundaries and independent openings.
- Full Release: PASS, 6/6, including research and UCI; see `release.log`.
- Existing formal/archived output protections remain unchanged and tested.
- An earlier 4-game R4-based smoke also passed before latest-main integration;
  final evidence and statistics above refer only to the latest 8-game match.

The raw PGN, version record, exact fastchess argument array/configuration and
logs remain in `.tools/elo/latest/`; candidate build log/manifest and per-platform
baseline cache are under `.tools/elo/`. These are intentionally disposable and
ignored by Git. Same-source, clock-limited smoke outcomes establish the working
loop only; the displayed Elo is descriptive, not a strength claim.

## Delivery

Windows physical-host match: NOT_RUN. The wrapper uses portable pathlib,
argument arrays, Ninja Release and platform-specific executable/cache names.
Pushed-sha existing GitHub Actions verification: pending. No workflow was changed.

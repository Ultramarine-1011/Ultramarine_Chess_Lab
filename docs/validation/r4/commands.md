# R4 command/evidence index

All commands run from repository root on macOS; `.venv` dependencies from
requirements.lock. See VALIDATION.md for tested revision/dirty-state attribution.

## Preregistration

```
cmake --preset release -DPython3_EXECUTABLE="$PWD/.venv/bin/python"
cmake --build --preset release --parallel 4
ctest --preset release
```

Logs `plan-{configure,build,release}.log`, revision 0d7a4f5+dirty protocol/docs only.

## R4.1

```
.venv/bin/python -m ucl.r4_data acquire --output experiments/results/r4-data-v1
ctest --preset release -R '^research$'
ctest --preset release
.venv/bin/python -m ucl.r4_data validate --output experiments/results/r4-data-v1
```

Logs r41-acquire/targeted/release/audit.log. Preregistration4e1bb70+dirty R4.1.
Raw bounded prefixes `.tools/r4-sources`; selected CC0 PGNs in dataset bundle.

## R4.2 / R4.3

```
# clean37d7280: configure/build commands above, then
.venv/bin/python -c 'from ucl.feature_data import export_dataset; export_dataset("experiments/results/r4-data-v1", "build/release/ucl", "experiments/results/r4-features-v1")'
OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python -m ucl.r4_training --output experiments/results/r4-baselines-v1
# clean a0c3443, provenance correction only:
OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python -m ucl.r4_training --output experiments/results/r4-baselines-v2
# a0c3443+dirty R4.3:
ctest --preset release -R '^(unit|perft|research|uci|experiments)$'
ctest --preset release
cmake --preset debug -DPython3_EXECUTABLE="$PWD/.venv/bin/python"
cmake --build --preset debug --parallel 4
ctest --preset debug
cmake --preset sanitize -DPython3_EXECUTABLE="$PWD/.venv/bin/python"
cmake --build --preset sanitize --parallel 4
ctest --preset sanitize
.tools/bin/fastchess --compliance "$PWD/build/release/ucl"
.venv/bin/python -m ucl.r4_openings acquire --output experiments/results/r4-openings-v1
```

Original compliance stdout retained gzip (ANSI/CR bytes preserved).
First fixture assertion failure retained; final Release/Debug/sanitizer logs labeled final.

## R4.4 candidate freeze and formal run

Clean benchmark code `deab47005cad0615d7f150e008c33cb2017311bf`; same Release
configure/build as above, logs in `.tools/r4-benchmark-build`.

```
.venv/bin/ucl-lab benchmark --config experiments/configs/r4/refit8-benchmark.json --output experiments/results/r4-benchmarks-v1/refit8
# same commands for pawn / king / full, each followed by:
.venv/bin/ucl-lab validate experiments/results/r4-benchmarks-v1/<group>/record.json
.venv/bin/ucl-lab report experiments/results/r4-benchmarks-v1/<group>/record.json
.venv/bin/python -m ucl.r4_experiment freeze
```

Four raw bundles retain actual UCI identity, model copies, 480 search queries and
280 static repeats. Freeze points to each record hash. Logging extension only
adds observations; telemetry smoke is 4 games, both same Handcrafted, dirty
prototype, depth2 and existing smoke openings. `r44-telemetry-smoke.log` verifies
all374 moves have final stats; this diagnostic does not select model or openings.

Formal commands are in README; output `experiments/results/r4-match-final-20261015`
is unique, 400 games/200 pairs. If `record.json` already exists, inspect process/
status before any action; never restart just because a tool observation times out.

## Fixed-sample protocol recovery

Original run625d84e actually failed after120 completed games, rather than being
lost to a tool observation timeout. Full raw bundle remains failed and immutable.

```
gh run view 38729565254 --log-failed
# exact protocol+Windows fixture repair;625d84e+dirty:
cmake --preset release -DPython3_EXECUTABLE="$PWD/.venv/bin/python"
cmake --build --preset release --parallel 4
ctest --preset release -R '^(uci|experiments)$'
ctest --preset release
# likewise debug/sanitize configure/build/ctest; logs r44-recovery-*
.tools/bin/fastchess --compliance "$PWD/build/release/ucl"
.venv/bin/python -m ucl.r4_study prepare
.venv/bin/python -m ucl.r4_results experiments/results/r4-match-final-20261015/record.json --completed-prefix-games 120 --output experiments/results/r4-recovery-v1/prefix-analysis.json
```

The ordinary validator continues to reject the failed run. The explicit prefix
operation checks all source hashes, all120 legal PGNs and60 full paired rounds;
156 orphan queries in unfinished121 are preserved separately and excluded from
move-cost totals. The recovery plan was saved before continuing the remaining
original openings, with unchanged model/clock/total200 pairs and a frozen UCI-only
patch. Record each batch's binary identity; never describe this as one uninterrupted run.

## R4.5 final evidence

```
.venv/bin/ucl-lab validate experiments/results/r4-match-continuation-20261015/record.json
.venv/bin/python -m ucl.r4_study finalize
.venv/bin/python -m ucl.r4_study validate
.venv/bin/python docs/validation/r4/audit_final.py
.venv/bin/python scripts/build_revision.py 625d84e370395cfd013eeac429b059bb107ca33d
python3 -m venv .tools/r4-plot-env
.tools/r4-plot-env/bin/python -m pip install -r docs/validation/r4/plot-requirements.txt
.tools/r4-plot-env/bin/python docs/validation/r4/plot_results.py
```

Matplotlib isolated from locked engine/training environment. PNGs visually checked;
SVG metadata Date removed and hash salt fixed. Figures use stored metrics only.
Both formal binaries retained locally; prefix rebuild exactly reproduces the
recorded SHA-256. Formal clocks do not guarantee replay-identical games across runs.

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

# Exact R3 validation commands

Working directory: repository root; macOS Apple Silicon development host.
Logs use full preset CTest commands below; binaries configured with .venv Python.

R3.1 base fcc6523: parent b9fac65cbcb68b492090b076f333dff861580a86 + dirty R3.1.
R3.2 base: 5065f0962e5023576080961c76574697af35e7b0 + dirty R3.2.

```sh
cmake --preset release -DPython3_EXECUTABLE="$PWD/.venv/bin/python"
cmake --build --preset release --parallel 4
ctest --preset release -R '^(unit|perft|research)$'
ctest --preset release
cmake --preset debug -DPython3_EXECUTABLE="$PWD/.venv/bin/python"
cmake --build --preset debug --parallel 4
ctest --preset debug
cmake --preset sanitize -DPython3_EXECUTABLE="$PWD/.venv/bin/python"
cmake --build --preset sanitize --parallel 4
ctest --preset sanitize
```

R3.1 targeted command: `ctest --preset release -R '^(experiments|research)$'`.
R3.2 initial test called LegalMoveGenerator as function; corrected to property.
Initial diagnostic feature export uses dirty binary, retained locally at
`.tools/r3-features-diagnostic`; formal export uses a clean committed binary.

## R3.5 formal execution and acceptance

Formal clean code/binary: 476ceeee4b96d0ee1f2ffcf1f572f08833c4bf70.
C++ source remained unchanged after this experiment; final setup fix aligns the
Python minimum to NumPy/SciPy's >=3.12 requirement. Final local acceptance tests
use that SHA plus dirty archive/docs/setup metadata and retain configure/build logs.

```sh
.venv/bin/ucl-lab benchmark --config experiments/configs/r3-benchmark.json --output experiments/results/r3-benchmark-final-20261015
.venv/bin/ucl-lab match --config experiments/configs/r3-match.json --output experiments/results/r3-match-final-20261015 --fastchess .tools/bin/fastchess
.venv/bin/ucl-lab validate experiments/results/r3-benchmark-final-20261015/record.json
.venv/bin/ucl-lab validate experiments/results/r3-match-final-20261015/record.json
.venv/bin/ucl-lab report experiments/results/r3-benchmark-final-20261015/record.json
.venv/bin/ucl-lab report experiments/results/r3-match-final-20261015/record.json
.venv/bin/python docs/validation/r3/audit_final.py
cmake --preset release -DPython3_EXECUTABLE="$PWD/.venv/bin/python"
cmake --build --preset release --parallel 4
ctest --preset release
.venv/bin/python -m pip check
```

Output directories refuse reuse; do not repeat the formal match to reproduce the
audit. The audit only reads retained evidence. test-results.json was produced by
one official `scripts/train_linear.py test` operation; never rerun it to tune.
Exact formal binary also retained locally under `.tools/r3-frozen-engine-476ceee`.

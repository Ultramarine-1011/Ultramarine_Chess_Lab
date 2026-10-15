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

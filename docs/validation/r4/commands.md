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

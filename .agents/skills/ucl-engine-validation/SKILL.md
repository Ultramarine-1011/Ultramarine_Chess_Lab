---
name: ucl-engine-validation
description: Validate UCL engine changes and regressions with existing CTest, Perft, search and UCI checks; collect milestone evidence. Use for engine correctness or acceptance, not statistical experiment conclusions.
---

# UCL engine validation

Work from the repository root. Follow [AGENTS.md](../../../AGENTS.md) and the
authorized scope in [ROADMAP.md](../../../ROADMAP.md); a validation request does
not authorize the next research stage.

Read the latest [VALIDATION.md](../../../VALIDATION.md) entry and linked evidence,
the changed source/tests and [ARCHITECTURE.md](../../../ARCHITECTURE.md) before
selecting checks. Inspect Git state and current Actions runs. Use the build and
environment commands in [README.md](../../../README.md), including the Windows
Developer PowerShell and `.venv/Scripts/python.exe` variants. Do not assume a
cached binary represents HEAD: reconfigure and build the selected preset.

## Select existing checks

`CMakeLists.txt` is the source of truth for test names and wiring. From the root,
run `ctest --preset release -N` to inspect the available tests, then choose:

| Changed behavior | Targeted command | Evidence inspected |
| --- | --- | --- |
| Position, features, evaluation | `ctest --preset release -R '^(unit|perft)$'` | `tests/core_tests.cpp`, affected public interfaces |
| Search, limits, terminal/history, QS/TT/PV | `ctest --preset release -R '^search$'` | existing exhaustive/reference and option-combination checks |
| UCI protocol, stop, options, process lifecycle | `ctest --preset release -R '^uci$'` | real executable exercised by `tests/test_uci.py` |
| Experiment tooling | `ctest --preset release -R '^experiments$'` | `tests/test_experiments.py` |

Reuse those tests and fixtures; add coverage only for behavior they do not
already exercise. Preserve the score/feature perspectives, terminal-before-static
evaluation, and legal-move checks described in the architecture. Match assertions
to search semantics: QS changes the horizon, and TT PVs can be legal prefixes.

After targeted checks, run `ctest --preset release` before a milestone commit.
For C++ memory/lifetime/search changes or full engine acceptance, also use the
existing Debug and macOS sanitizer presets as appropriate; follow
[CI](../../../.github/workflows/ci.yml) for the supported platform matrix.
For a request limited to Skills/docs, a Release regression run is sufficient.
Use existing fastchess compliance/smoke commands only when process/match
compatibility is in scope; a smoke result cannot establish playing strength.

## Finish with attributable evidence

Record tested full SHA, dirty state, exact commands, toolchain/host, results,
failures and unrun checks in VALIDATION.md or linked small logs. Keep local
results, hosted macOS/Windows CI and the user's Windows experiment host distinct.
When a push is authorized, inspect runs for the pushed SHA and report pending or
failed jobs accurately. Handle a CI failure within existing authorization; a
validation skill does not grant additional mutation permission. Stop at the
agreed acceptance criteria.

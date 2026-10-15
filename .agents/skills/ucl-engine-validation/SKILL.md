---
name: ucl-engine-validation
description: Validate UCL engine changes with existing Perft, search and UCI checks.
---

Use the build commands in [README.md](../../../README.md).
CMakeLists.txt defines CTest groups: unit, search, perft, uci, experiments, research.
Choose groups matching changed behavior; broad engine/tooling refactors warrant
`ctest --preset release`. CI adds Windows/macOS Debug and sanitizers.

Preserve terminal-before-static evaluation, legal moves and score perspectives
from [ARCHITECTURE.md](../../../ARCHITECTURE.md). Check real executable behavior
for UCI/model changes. Summarize commands, outcomes and relevant limitations;
no separate audit bundle or mandatory logbook for ordinary development.

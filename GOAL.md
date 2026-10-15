# R5 Evaluation Efficiency & Search Budget Study

Authorized 2026-10-16 (Asia/Singapore): complete R5.1–R5.5, including Windows
experiments, stage commits/pushes and CI repair; stop after R5, do not start R6.

Execution contract: [docs/r5/protocol.md](docs/r5/protocol.md).
Live evidence and recovery state: [VALIDATION.md](VALIDATION.md).

| Stage | Acceptance |
|---|---|
| R5.1 | Frozen protocol/200 reproducible independent openings/four parsed controls; clean Windows Original baseline and smoke tests |
| R5.2 | Profile-led local optimization; exact features/raw score/cp on all 44681 retained positions, seeded legal and edge positions; deterministic search equality |
| R5.3 | Alternating repeated static/depth/nodes measurements with raw logs, clean identities and host conditions |
| R5.4 | Four fixed 400-game/200-pair controls, same openings, fixed tool/model/options, complete UCI telemetry and terminal audit |
| R5.5 | Rebuilt paired statistics, uncertainty/multiplicity, honest causal limits, final report and required documentation, clean tests and GitHub CI |

Handcrafted remains default. R4 weights, features, data and raw results are frozen.
No retraining, tuning on opened test data, or new search algorithms. Failed runs
and candidates remain evidence. A valid negative study can pass engineering
acceptance; measured playing-strength improvement is a separate hypothesis.

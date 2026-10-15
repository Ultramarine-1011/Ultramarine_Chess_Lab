---
name: ucl-experiment-audit
description: Analyze UCL experiment bundles and assess statistical claims using retained evidence.
---

`ucl-lab report <bundle>/record.json` already verifies artifacts and recomputes
statistics; use `validate` only when no report is needed. Historical binaries
are unnecessary for offline analysis. R4's two-batch aggregate can be checked
with `python -m ucl.r4_study`.

Follow [EXPERIMENTS.md](../../../EXPERIMENTS.md) for pairing, held-out data and
uncertainty. Match claims to the actual sample, limits and hardware. Smoke
results do not establish Elo. An audit does not require rerunning experiments
or permanently recording another copy of the same evidence.

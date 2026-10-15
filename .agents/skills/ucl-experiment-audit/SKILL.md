---
name: ucl-experiment-audit
description: Audit UCL match, benchmark and ablation bundles for provenance, pairing, integrity and justified statistical claims using existing tools. Use for experiment evidence or strength claims, not ordinary engine regression checks.
---

# UCL experiment audit

Work from the repository root. Read [AGENTS.md](../../../AGENTS.md), the current
[ROADMAP.md](../../../ROADMAP.md), latest [VALIDATION.md](../../../VALIDATION.md)
and the requested record/config/report. Read the relevant procedures in
[EXPERIMENTS.md](../../../EXPERIMENTS.md) and interface details in
[ARCHITECTURE.md](../../../ARCHITECTURE.md). Auditing a retained bundle does not
require rebuilding its engines or rerunning its games on another host.

## Validate retained evidence first

Use the installed project CLI with the environment from [README.md](../../../README.md):

```text
ucl-lab validate <bundle>/record.json
ucl-lab report <bundle>/record.json
```

On Windows the executable is `.venv/Scripts/ucl-lab.exe`; on macOS it is
`.venv/bin/ucl-lab`. Paths in this skill are relative to the repository root.
`python/ucl/integrity.py` dispatches match and benchmark schemas and checks
artifact hashes, saved inputs and recomputed results. `report` also validates
before rendering. Reuse it; do not create a second PGN parser, statistics routine
or integrity checker. When investigating a failure, inspect its implementation
and existing `tests/test_experiments.py` / `tests/test_uci.py` coverage.

An integrity pass establishes internal consistency, not independent truth of
every metadata field or adequacy of the experimental design. Check the evidence:

| Evidence | Audit focus |
| --- | --- |
| Identity | full revisions, dirty states, binary hashes, build manifests, compiler/flags and actual UCI build info |
| Controls | revision comparison uses distinct builds with matched compiler controls; ablation uses one binary with explicit different options |
| Matches | frozen opening source/hash, swapped colors, independent round count, seed, limits, concurrency, adjudication and abnormal terminations |
| Statistics | W/D/L, five paired-score counts, bootstrap resampling by round and retained uncertainty; repeated seeds are not new independent samples |
| Benchmarks | frozen positions/options, same QS semantics for speed claims, completed depth and final versus last-completed counters, raw timing/NPS/TT data |
| Host | actual CPU/OS/toolchain/power/resource record; distinguish hosted Windows CI from the user's sustained experiment host |

Use `scripts/build_revision.py` and `scripts/prepare_comparison.py` only if new
comparisons are authorized; use existing CLI runners for execution. Follow the
clean-build and unique-output-directory procedures in README/EXPERIMENTS. Retain
failed or superseded bundles without rewriting them. Dirty diagnostic runs must
remain labeled diagnostics. Do not start a long experiment from an audit request.

## Report the supported conclusion

Separate integrity, correctness, tactical fixtures, measured performance and
playing strength. Smoke games and the R2 16-game sample do not justify Elo gains.
Three timing repeats do not establish significance; the current paired bootstrap
is descriptive and the tooling provides no SPRT. Identify missing evidence and
unrun target-host checks instead of supplying invented results or new statistics.
Record commands, audited revisions, conclusions and limitations in VALIDATION.md
or a linked audit note. Keep large raw artifacts out of Git; preserve existing
evidence when selecting a small reviewable bundle.

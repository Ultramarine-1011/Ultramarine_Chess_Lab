# UCL search benchmark

Revision: `eee9d44b5a73b36f06ae837e079a6afc66f8caaf`; dirty: False

Per-position medians; wall time includes UCI round trip and TT allocation. Single search thread; cold TT per query.

| Engine | Limit | Nodes | Wall ms | Wall NPS | Tactical checks |
|---|---|---:|---:|---:|---:|
| R1 | {'depth': 1} | 165 | 2.92 | 56450 | 5/6 |
| R1 | {'depth': 4} | 91000 | 13.31 | 6836472 | 6/6 |
| R2 | {'depth': 1} | 3223 | 7.04 | 457626 | 6/6 |
| R2 | {'depth': 4} | 266968 | 80.02 | 3336256 | 6/6 |
| R2-reference | {'depth': 1} | 165 | 3.02 | 54615 | 5/6 |
| R2-reference | {'depth': 4} | 91000 | 14.16 | 6428237 | 6/6 |

QS changes leaf semantics. Tactical labels are narrow regression checks; this suite and throughput do not measure Elo.
R1 lacks final interrupted-search counters; its node-limited totals are last completed iteration only. Compare R1 at fixed depth.

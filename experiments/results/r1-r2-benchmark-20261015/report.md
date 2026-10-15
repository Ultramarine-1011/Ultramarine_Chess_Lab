# UCL search benchmark

Revision: `046d5b043ec5072238e8708c9f0df8e9d57834ee`; dirty: False

Per-position medians; wall time includes UCI round trip and TT allocation. Single search thread; cold TT per query.

| Engine | Limit | Nodes | Wall ms | Wall NPS | Tactical checks |
|---|---|---:|---:|---:|---:|
| R1 | {'depth': 1} | 165 | 2.81 | 58717 | 5/6 |
| R1 | {'depth': 4} | 91000 | 13.66 | 6659369 | 6/6 |
| R2 | {'depth': 1} | 3223 | 7.16 | 450397 | 6/6 |
| R2 | {'depth': 4} | 266968 | 77.50 | 3444867 | 6/6 |
| R2-reference | {'depth': 1} | 165 | 2.91 | 56650 | 5/6 |
| R2-reference | {'depth': 4} | 91000 | 13.99 | 6505421 | 6/6 |

QS changes leaf semantics. Tactical labels are narrow regression checks; this suite and throughput do not measure Elo.
R1 lacks final interrupted-search counters; its node-limited totals are last completed iteration only. Compare R1 at fixed depth.

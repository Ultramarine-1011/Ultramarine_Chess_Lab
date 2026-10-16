# UCL search benchmark

Mode: formal; revision: `1ca065aed204607b683d9727afdff714d6977314`; dirty: True

Per-position medians; wall time includes UCI round trip and TT allocation. Single search thread; cold TT per query.

| Engine | Limit | Nodes | Wall ms | Wall NPS | Tactical checks |
|---|---|---:|---:|---:|---:|
| G | {'depth': 4} | 148869 | 138.84 | 1072203 | 6/6 |
| G | {'nodes': 50000} | 300998 | 160.47 | 1875710 | 6/6 |
| Handcrafted | {'depth': 4} | 266968 | 174.98 | 1525712 | 6/6 |
| Handcrafted | {'nodes': 50000} | 300994 | 140.78 | 2138006 | 6/6 |
| M08 | {'depth': 4} | 145888 | 131.36 | 1110631 | 6/6 |
| M08 | {'nodes': 50000} | 301000 | 161.94 | 1858731 | 6/6 |
| T | {'depth': 4} | 178044 | 137.72 | 1292770 | 6/6 |
| T | {'nodes': 50000} | 301000 | 163.95 | 1835895 | 6/6 |

QS changes leaf semantics. Tactical labels are narrow regression checks; this suite and throughput do not measure Elo.
R1 lacks final interrupted-search counters; its node-limited totals are last completed iteration only. Compare R1 at fixed depth.

# UCL search benchmark

Mode: exploratory; revision: `3524319eaea508b36fb4ccf4a34e65fd8a6d5e87`; dirty: True

Per-position medians; wall time includes UCI round trip and TT allocation. Single search thread; cold TT per query.

| Engine | Limit | Nodes | Wall ms | Wall NPS | Tactical checks |
|---|---|---:|---:|---:|---:|
| G | {'depth': 4} | 406855 | 286.58 | 1419672 | 0/0 |
| G | {'nodes': 50000} | 500000 | 312.18 | 1601651 | 0/0 |
| Handcrafted | {'depth': 4} | 408877 | 255.60 | 1599678 | 0/0 |
| Handcrafted | {'nodes': 50000} | 500000 | 268.93 | 1859247 | 0/0 |
| M08 | {'depth': 4} | 430882 | 306.71 | 1404867 | 0/0 |
| M08 | {'nodes': 50000} | 500000 | 311.95 | 1602839 | 0/0 |
| T | {'depth': 4} | 431618 | 300.25 | 1437529 | 0/0 |
| T | {'nodes': 50000} | 500000 | 312.76 | 1598690 | 0/0 |

QS changes leaf semantics. Tactical labels are narrow regression checks; this suite and throughput do not measure Elo.
R1 lacks final interrupted-search counters; its node-limited totals are last completed iteration only. Compare R1 at fixed depth.

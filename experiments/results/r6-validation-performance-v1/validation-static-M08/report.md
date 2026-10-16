# UCL search benchmark

Mode: exploratory; revision: `3524319eaea508b36fb4ccf4a34e65fd8a6d5e87`; dirty: True

Per-position medians; wall time includes UCI round trip and TT allocation. Single search thread; cold TT per query.

| Engine | Limit | Nodes | Wall ms | Wall NPS | Tactical checks |
|---|---|---:|---:|---:|---:|
| Handcrafted | {'depth': 1} | 1570 | 37.02 | 42408 | 0/0 |
| M08 | {'depth': 1} | 1450 | 36.50 | 39728 | 0/0 |

Static evaluation: mean of per-position median ns/call (7 alternating repeats, 100000 calls/model/position):
Handcrafted 56.58 ns; Linear 142.14 ns.
Raw static measurements and checksums are retained separately; repeated timings are descriptive, not a significance test.

QS changes leaf semantics. Tactical labels are narrow regression checks; this suite and throughput do not measure Elo.
R1 lacks final interrupted-search counters; its node-limited totals are last completed iteration only. Compare R1 at fixed depth.

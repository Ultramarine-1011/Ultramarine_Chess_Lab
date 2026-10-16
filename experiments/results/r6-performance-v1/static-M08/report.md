# UCL search benchmark

Mode: formal; revision: `1ca065aed204607b683d9727afdff714d6977314`; dirty: True

Per-position medians; wall time includes UCI round trip and TT allocation. Single search thread; cold TT per query.

| Engine | Limit | Nodes | Wall ms | Wall NPS | Tactical checks |
|---|---|---:|---:|---:|---:|
| Handcrafted | {'depth': 1} | 3223 | 39.51 | 81569 | 6/6 |
| M08 | {'depth': 1} | 1578 | 38.01 | 41515 | 6/6 |

Static evaluation: mean of per-position median ns/call (7 alternating repeats, 100000 calls/model/position):
Handcrafted 50.16 ns; Linear 111.28 ns.
Raw static measurements and checksums are retained separately; repeated timings are descriptive, not a significance test.

QS changes leaf semantics. Tactical labels are narrow regression checks; this suite and throughput do not measure Elo.
R1 lacks final interrupted-search counters; its node-limited totals are last completed iteration only. Compare R1 at fixed depth.

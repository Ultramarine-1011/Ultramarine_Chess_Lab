# UCL search benchmark

Revision: `476ceeee4b96d0ee1f2ffcf1f572f08833c4bf70`; dirty: False

Per-position medians; wall time includes UCI round trip and TT allocation. Single search thread; cold TT per query.

| Engine | Limit | Nodes | Wall ms | Wall NPS | Tactical checks |
|---|---|---:|---:|---:|---:|
| Handcrafted | {'depth': 3} | 82410 | 29.40 | 2802875 | 6/6 |
| Handcrafted | {'depth': 4} | 266968 | 76.15 | 3505689 | 6/6 |
| Linear | {'depth': 3} | 134403 | 42.48 | 3164276 | 6/6 |
| Linear | {'depth': 4} | 287201 | 81.24 | 3535016 | 6/6 |

Static evaluation: mean of per-position median ns/call (7 alternating repeats, 100000 calls/model/position):
Handcrafted 23.02 ns; Linear 24.30 ns.
Raw static measurements and checksums are retained separately; repeated timings are descriptive, not a significance test.

QS changes leaf semantics. Tactical labels are narrow regression checks; this suite and throughput do not measure Elo.
R1 lacks final interrupted-search counters; its node-limited totals are last completed iteration only. Compare R1 at fixed depth.

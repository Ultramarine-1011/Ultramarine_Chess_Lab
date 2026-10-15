# UCL search benchmark

Revision: `deab47005cad0615d7f150e008c33cb2017311bf`; dirty: False

Per-position medians; wall time includes UCI round trip and TT allocation. Single search thread; cold TT per query.

| Engine | Limit | Nodes | Wall ms | Wall NPS | Tactical checks |
|---|---|---:|---:|---:|---:|
| Handcrafted | {'depth': 3} | 82410 | 29.35 | 2807976 | 6/6 |
| Handcrafted | {'depth': 4} | 266968 | 76.66 | 3482354 | 6/6 |
| refit8 | {'depth': 3} | 90355 | 32.10 | 2815218 | 6/6 |
| refit8 | {'depth': 4} | 249002 | 72.84 | 3418303 | 6/6 |

Static evaluation: mean of per-position median ns/call (7 alternating repeats, 100000 calls/model/position):
Handcrafted 24.79 ns; Linear 27.21 ns.
Raw static measurements and checksums are retained separately; repeated timings are descriptive, not a significance test.

QS changes leaf semantics. Tactical labels are narrow regression checks; this suite and throughput do not measure Elo.
R1 lacks final interrupted-search counters; its node-limited totals are last completed iteration only. Compare R1 at fixed depth.

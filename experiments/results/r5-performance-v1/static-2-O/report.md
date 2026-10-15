# UCL search benchmark

Revision: `97621be5b2b23ff6c71b1e5d22dfad2c3366cd91`; dirty: False

Per-position medians; wall time includes UCI round trip and TT allocation. Single search thread; cold TT per query.

| Engine | Limit | Nodes | Wall ms | Wall NPS | Tactical checks |
|---|---|---:|---:|---:|---:|
| Handcrafted | {'depth': 3} | 82410 | 75.63 | 1089627 | 6/6 |
| OriginalFull14 | {'depth': 3} | 84320 | 95.58 | 882197 | 6/6 |

Static evaluation: mean of per-position median ns/call (7 alternating repeats, 100000 calls/model/position):
Handcrafted 47.63 ns; Linear 158.77 ns.
Raw static measurements and checksums are retained separately; repeated timings are descriptive, not a significance test.

QS changes leaf semantics. Tactical labels are narrow regression checks; this suite and throughput do not measure Elo.
R1 lacks final interrupted-search counters; its node-limited totals are last completed iteration only. Compare R1 at fixed depth.

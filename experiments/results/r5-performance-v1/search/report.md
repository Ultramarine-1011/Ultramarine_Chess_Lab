# UCL search benchmark

Revision: `97621be5b2b23ff6c71b1e5d22dfad2c3366cd91`; dirty: False

Per-position medians; wall time includes UCI round trip and TT allocation. Single search thread; cold TT per query.

| Engine | Limit | Nodes | Wall ms | Wall NPS | Tactical checks |
|---|---|---:|---:|---:|---:|
| Handcrafted | {'depth': 3} | 82410 | 78.22 | 1053572 | 6/6 |
| Handcrafted | {'depth': 4} | 266968 | 153.70 | 1736936 | 6/6 |
| Handcrafted | {'nodes': 50000} | 300994 | 128.46 | 2343029 | 6/6 |
| OptimizedFull14 | {'depth': 3} | 84320 | 88.81 | 949467 | 6/6 |
| OptimizedFull14 | {'depth': 4} | 195889 | 146.59 | 1336314 | 6/6 |
| OptimizedFull14 | {'nodes': 50000} | 300974 | 158.34 | 1900750 | 6/6 |
| OriginalFull14 | {'depth': 3} | 84320 | 95.75 | 880609 | 6/6 |
| OriginalFull14 | {'depth': 4} | 195889 | 161.54 | 1212603 | 6/6 |
| OriginalFull14 | {'nodes': 50000} | 300974 | 169.82 | 1772347 | 6/6 |

QS changes leaf semantics. Tactical labels are narrow regression checks; this suite and throughput do not measure Elo.
R1 lacks final interrupted-search counters; its node-limited totals are last completed iteration only. Compare R1 at fixed depth.

# UCL search benchmark

Revision: `046d5b043ec5072238e8708c9f0df8e9d57834ee`; dirty: False

Per-position medians; wall time includes UCI round trip and TT allocation. Single search thread; cold TT per query.

| Engine | Limit | Nodes | Wall ms | Wall NPS | Tactical checks |
|---|---|---:|---:|---:|---:|
| q0t0p0 | {'depth': 1} | 165 | 2.93 | 56356 | 5/6 |
| q0t0p0 | {'depth': 4} | 91000 | 13.40 | 6790263 | 6/6 |
| q0t0p0 | {'nodes': 10000} | 60905 | 9.58 | 6356604 | 6/6 |
| q0t0p1 | {'depth': 1} | 165 | 2.87 | 57563 | 5/6 |
| q0t0p1 | {'depth': 4} | 41677 | 8.72 | 4777966 | 6/6 |
| q0t0p1 | {'nodes': 10000} | 60905 | 9.76 | 6239280 | 6/6 |
| q0t1p0 | {'depth': 1} | 165 | 10.46 | 15779 | 5/6 |
| q0t1p0 | {'depth': 4} | 76552 | 18.55 | 4127367 | 6/6 |
| q0t1p0 | {'nodes': 10000} | 60905 | 16.25 | 3748538 | 6/6 |
| q0t1p1 | {'depth': 1} | 165 | 9.61 | 17178 | 5/6 |
| q0t1p1 | {'depth': 4} | 18411 | 13.17 | 1397658 | 6/6 |
| q0t1p1 | {'nodes': 10000} | 60905 | 16.84 | 3617483 | 6/6 |
| q1t0p0 | {'depth': 1} | 3223 | 3.90 | 826932 | 6/6 |
| q1t0p0 | {'depth': 4} | 389687 | 90.74 | 4294356 | 6/6 |
| q1t0p0 | {'nodes': 10000} | 60994 | 12.27 | 4970733 | 6/6 |
| q1t0p1 | {'depth': 1} | 3223 | 3.93 | 819763 | 6/6 |
| q1t0p1 | {'depth': 4} | 333568 | 90.97 | 3666679 | 6/6 |
| q1t0p1 | {'nodes': 10000} | 60994 | 12.83 | 4752409 | 6/6 |
| q1t1p0 | {'depth': 1} | 3223 | 10.49 | 307146 | 6/6 |
| q1t1p0 | {'depth': 4} | 369510 | 94.19 | 3923011 | 6/6 |
| q1t1p0 | {'nodes': 10000} | 60994 | 18.86 | 3234676 | 6/6 |
| q1t1p1 | {'depth': 1} | 3223 | 10.67 | 302107 | 6/6 |
| q1t1p1 | {'depth': 4} | 266968 | 79.04 | 3377432 | 6/6 |
| q1t1p1 | {'nodes': 10000} | 60994 | 19.55 | 3119100 | 6/6 |

QS changes leaf semantics. Tactical labels are narrow regression checks; this suite and throughput do not measure Elo.
R1 lacks final interrupted-search counters; its node-limited totals are last completed iteration only. Compare R1 at fixed depth.

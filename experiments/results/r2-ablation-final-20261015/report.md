# UCL search benchmark

Revision: `eee9d44b5a73b36f06ae837e079a6afc66f8caaf`; dirty: False

Per-position medians; wall time includes UCI round trip and TT allocation. Single search thread; cold TT per query.

| Engine | Limit | Nodes | Wall ms | Wall NPS | Tactical checks |
|---|---|---:|---:|---:|---:|
| q0t0p0 | {'depth': 1} | 165 | 3.16 | 52268 | 5/6 |
| q0t0p0 | {'depth': 4} | 91000 | 14.64 | 6217952 | 6/6 |
| q0t0p0 | {'nodes': 10000} | 60905 | 10.74 | 5672815 | 6/6 |
| q0t0p1 | {'depth': 1} | 165 | 3.44 | 47964 | 5/6 |
| q0t0p1 | {'depth': 4} | 41677 | 10.50 | 3970451 | 6/6 |
| q0t0p1 | {'nodes': 10000} | 60905 | 10.84 | 5617914 | 6/6 |
| q0t1p0 | {'depth': 1} | 165 | 10.17 | 16221 | 5/6 |
| q0t1p0 | {'depth': 4} | 76552 | 20.39 | 3754973 | 6/6 |
| q0t1p0 | {'nodes': 10000} | 60905 | 17.16 | 3548260 | 6/6 |
| q0t1p1 | {'depth': 1} | 165 | 9.71 | 16998 | 5/6 |
| q0t1p1 | {'depth': 4} | 18411 | 14.40 | 1278834 | 6/6 |
| q0t1p1 | {'nodes': 10000} | 60905 | 17.87 | 3408711 | 6/6 |
| q1t0p0 | {'depth': 1} | 3223 | 4.43 | 728122 | 6/6 |
| q1t0p0 | {'depth': 4} | 389687 | 111.08 | 3508107 | 6/6 |
| q1t0p0 | {'nodes': 10000} | 60994 | 14.01 | 4352582 | 6/6 |
| q1t0p1 | {'depth': 1} | 3223 | 4.52 | 713342 | 6/6 |
| q1t0p1 | {'depth': 4} | 333568 | 107.90 | 3091326 | 6/6 |
| q1t0p1 | {'nodes': 10000} | 60994 | 14.21 | 4291373 | 6/6 |
| q1t1p0 | {'depth': 1} | 3223 | 11.19 | 287916 | 6/6 |
| q1t1p0 | {'depth': 4} | 369510 | 109.58 | 3372074 | 6/6 |
| q1t1p0 | {'nodes': 10000} | 60994 | 20.34 | 2998409 | 6/6 |
| q1t1p1 | {'depth': 1} | 3223 | 11.16 | 288928 | 6/6 |
| q1t1p1 | {'depth': 4} | 266968 | 93.59 | 2852537 | 6/6 |
| q1t1p1 | {'nodes': 10000} | 60994 | 20.60 | 2960832 | 6/6 |

QS changes leaf semantics. Tactical labels are narrow regression checks; this suite and throughput do not measure Elo.
R1 lacks final interrupted-search counters; its node-limited totals are last completed iteration only. Compare R1 at fixed depth.

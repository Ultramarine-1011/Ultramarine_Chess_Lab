# R5 preregistered protocol

Frozen before any R5 formal result, 2026-10-16 Asia/Singapore. The commit containing
this document is the preregistration. Changes require an explicit dated amendment
in VALIDATION.md and a new freeze before affected formal runs. R4 is sealed.

## Questions and fixed comparisons

Does Full14's R4 loss persist when controlling the number of searched nodes?
Can strictly equivalent, local feature extraction reduce static cost and improve
time-limited playing strength? Which observations support evaluation/target
misalignment versus throughput hypotheses? These comparisons are not an additive
causal decomposition; positions and search trees differ between evaluators.

| Group | First engine (reported score) | Second engine | Budget |
|---|---|---|---|
| A | Original Full14 | Handcrafted | 1+0.01 seconds |
| B | Original Full14 | Handcrafted | 50000 nodes/move; 1000+10 seconds clock guard |
| C | Optimized Full14 | Handcrafted | 1+0.01 seconds |
| D | Optimized Full14 | Original Full14 | 1+0.01 seconds |

Each group: same 200 openings in frozen sequential order, two games/opening with
colors exchanged, 400 games, total 1600. Run A,B,C,D sequentially, concurrency=1,
one search thread, Hash=16 MiB, Quiescence/UseTT/PVOrdering=true,
MoveOverhead=10 ms, maxmoves=150, no score resignation/draw adjudication or SPRT.
The node clock guard is deliberately much larger than 50000-node search time;
preflight must show actual `go ... nodes 50000` and final counters. Searches may
end below the limit for terminal/solved/max-depth positions; every undershoot is
classified against board state, iteration trace and clock guard. A clock-driven
undershoot invalidates the fixed-node claim. Do not replace nodes with time.

## Identities and preflight

Original is clean `f933fe24ed983cb011b7a1bb0b9382c36a9b8d11`, independently built
using scripts/build_revision.py. Optimized is a later clean isolated build with
identical compiler/build type/flags. Preserve both binaries locally and manifests
in Git. Handcrafted uses Original. Actual UCI evaluator identity must be checked.
Frozen Full14 file: experiments/results/r4-models-v1/full.txt, SHA-256
`43e2e1ad509bfef9a529ce98706d6b64004d50166e115d7871a7666b05dd728e`.
No model/test selection or training. Preserve R3/R4 tracked artifact hashes.

Reuse Windows 11 / Ryzen 9 8940HX, standard MSVC 19.51 toolchain, CMake 4.4.4,
venv and local MSVC include-prefix fix. Use official fastchess v1.8.2-alpha
(f618e34540f94f4719ad3817950618dabe441318) for *all* R5 formal matches;
record executable SHA-256 and help/version. R4 Mac used different hardware,
compiler and fastchess revision; never pool timing or match outcomes across them.
Run inexpensive UCI and real fastchess time/nodes telemetry smoke first, then
Release CTest before each stage commit. No toolchain reinstall absent a fault.

## Independent openings, frozen before acquisition/results

Use Lichess CC0 standard rated **2017-09**, HTTP Range first 3 MiB compressed,
at most first 4000 complete games, at most 48 MiB decompression, discarding the
partial tail. Reuse r4_data.bounded_source and dataset.prepare filters (standard,
normal ending, both ratings>=1500, base>=180 s, >=32 ply). Seed=20261016.
Sort eligible games by SHA256(seed:game_id), take first 200 unique legal
nonterminal 12-ply positions. Exclude exact/color-mirrored R3/R4 formal openings,
retained R3/R4 position keys, full-game identities and source Site identities;
also compare the first 12 plies of every reconstructable R3/R4 source game.
No evaluator score enters selection. Save source PGN, source HTTP/hash metadata,
selection/exclusion hashes and EPD; reconstruct offline to validate. If fewer
than 200 remain, mark BLOCKED_INPUT; do not silently choose a new month/cap.
FEN/EPD resets pre-opening history and counters equally for both engines.
CC0/source: https://database.lichess.org/ .

## Equivalence and optimization gate

Profile Original before choosing changes. Optimize only InterpretableFeatures
within the existing boundary. No incremental search state unless clear evidence
requires it. Feature version/names/order/signs/values and frozen model bytes must
remain exact. Compare all 44681 retained R4 FENs plus 2048 deterministic random
legal positions (seed 20261016), their mirrors, and explicit promotion, castling,
en-passant, pawn/king/endgame boundaries. Compare feature output, unrounded
double white_score and rounded side-to-move cp exactly, not within a tolerance.
Compare Original/Optimized moves, PV, score, depth, nodes, qnodes and TT/order
counters under fixed depth 3/4 and nodes=50000 on the R2 suite plus 32 seeded
positions and all explicit boundaries. No wall-clock cap in these comparisons.
Any unexplained mismatch rejects candidate deployment; preserve failure and
continue diagnostic A/B with PARTIAL status if necessary. Handcrafted and search
source remain unchanged. No weaker flags or fast-math to manufacture a gain.

## Performance and environment

R2 ten-position suite. Three paired outer blocks, alternating Original/Optimized
static benchmark order O-P/P-O/O-P; each existing static command contains seven
alternating Handcrafted/Linear repeats of 100000 calls per position. Same-binary
handcrafted control included. Fixed depth 3/4 and nodes=50000, five repetitions,
seeded engine-order shuffle through existing benchmark. Report per-position
medians then sums (search) or mean (static), block results and paired ratios.
Retain each query, PV, counters, transcript, failure, build manifest, OS/CPU,
power/AC/battery, available thermal sensors and background CPU snapshots.
No simultaneous heavy work during benchmarks/matches; no power-plan changes.
If temperature unavailable say so. Repeat variation is descriptive, not a claim
of independent hardware samples. Static speed target is a hypothesis (>0 gain),
not a gate requiring positive results; report zero/regression honestly.

## Statistics and interpretation (frozen analysis rules)

Report each group's W/D/L, score and five paired-score bins (0,.5,1,1.5,2),
normal terminal categories, maxmoves adjudication and every abnormal ending.
Resample 200 opening pairs with replacement 2000 times using seed 20261016,
percentile 95% descriptive interval, endpoints floor(.025*(1999)), ceil(.975*1999).
For the four planned claims vs score=.5, also report Bonferroni nominal 98.75%
intervals: floor(.00625*1999), ceil(.99375*1999), same bootstrap draws.
Confirmatory language requires corrected interval excluding .5; these approximate
conditional intervals do not guarantee coverage across opening families/hardware.
Use identical opening-index bootstrap draws across groups. Cross-group contrasts
C-A and B-A are paired exploratory diagnostics with 95% intervals and no new
confirmatory claim. Groups share openings; do not treat them as independent.
Elo-equivalent=400 log10(p/(1-p)), transform endpoints monotonically, infinite
endpoints explicit; conditional on this experiment, not a universal rating.
Separate facts, plausible inferences and untested hypotheses; no exact causal
allocation among semantics, static cost, nodes and throughput. Do not rerun R4
test metrics or refit models. Recommendations for R6 only, no implementation.

## Resource limits, stopping and recovery

Download cap 3 MiB; original source preserved compressed. Formal group process
timeout 6 hours; whole formal study at most 24 hours excluding troubleshooting.
Telemetry gzip is lossless; preserve raw SHA/size. Disk guard >=10 GiB free before
start. Stop on integrity/identity/illegal move/node-clock failure, never on score
or confidence interval. No early stopping, sample expansion, parameter/order
changes from results. Every formal output directory is exclusively created once.
Before restarting inspect running processes, record, PGN and logs. Preserve failed
record and all completed games permanently. Resume only missing games of original
indexed schedule, including an odd completed game; no completed game is replayed.
Freeze explicit recovery map and source/version/tool hashes before resumption;
if tool cannot schedule the exact missing color game, stop BLOCKED_ENV rather
than duplicate it. New run uses a new directory and discloses versions. A changed
search/evaluator invalidates pooling; protocol-only repair requires source audit.
Unresolvable environment failure: keep valid partial evidence, BLOCKED_ENV.

Stage acceptance is the GOAL.md table, with PASS/FAIL/PARTIAL/NOT_RUN/BLOCKED
recorded independently from the speed/strength hypotheses. Commit/push each
accepted stage, inspect matching macOS/Windows Actions, reconfigure/build after
each commit used for measurements. Final docs/r5/final-report.md is generated
from real bundles. Complete R5 and stop.

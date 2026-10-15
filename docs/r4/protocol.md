# R4 preregistered protocol — 2026-10-15

Authorization: R4.1–R4.5 objective supplied by the user. Start 0d7a4f5 (clean
main=origin/main); R3 frozen evidence is immutable. Handcrafted stays default
unless independent playing-strength evidence warrants a separately documented change.
No NNUE, RL or MCTS in R4. No paid compute. No R5 implementation.

## Data, frozen before acquisition

Lichess standard rated CC0 monthly exports 2017-02, 03, 04, 05, 06, 07 from
https://database.lichess.org/standard/lichess_db_standard_rated_YYYY-MM.pgn.zst .
License verified at https://database.lichess.org/ on 2026-10-15.
For each month request exactly bytes 0–3145727 (3 MiB maximum), retain at most
4000 complete PGNs; discard the final possibly truncated game. Total network cap
18 MiB; decompressed cap 48 MiB/source. This spreads coverage across six monthly
windows, but remains convenience prefix sampling within each month, not a uniform
platform sample. Do not add months or expand bounds based on outcomes.
Target >=4000 accepted games, >=20000 unique positions, >=6 distinct UTC dates;
report PARTIAL if missed. Preserve source URL, Range, HTTP headers, acquisition
UTC, hashes and selected source PGNs; raw compressed prefixes stay local .tools.

Reuse R3 legality, >=1500 ratings, base >=180s, Normal termination (including
resignation), distinct named players and >=32 plies. Retain at most 8 nonterminal
positions per game at plies16..160 with spacing7, selected by SHA256(seed,gid,ply).
Seed20261015. Game ID hashes starting FEN and complete mainline moves. Exact and
color-reflected position identities ignore counters and include side to move.
Remove all positions crossing splits, then retain one per position globally.

2017-02..05 source files are development: game hash split 80% train /20%
validation. 2017-06..07 files are independent future test: all games test, with
actual UTC timestamps checked to be strictly later than development. Date/split
assignment never uses results. Metadata diagnostics may inspect test dates, player
identities, ECO, label/phase frequencies but no fitted model losses before freeze.
Record player overlap; ordinary game-cluster inference does not remove cross-game
player dependence. Primary offline estimand is equal-game mean position loss;
position-weighted metrics are secondary. Bootstrap whole games (2000, fixed seed)
and report month-specific point estimates; only two future windows limit temporal
population inference. No position-iid error bars.

## Features and training, frozen before fitting

Preserve original handcrafted-v1 8 dimensions and exact evaluator behavior.
New interpretable-v2 has the same 8 then six white-minus-black dimensions:
8 isolated pawns: no friendly pawn on either adjacent file, regardless of rank;
9 doubled excess: sum max(pawn count on file -1,0);
10 passed advancement: each pawn with no opposing pawn ahead on same/adjacent file
contributes relative rank-1 (white rank2=>0; black mirrored), summed;
11 pawn shield: friendly pawns in king-adjacent files, one or two ranks forward;
12 attacked king ring: count of onboard king-neighbor squares attacked by opponent,
count each square once; pseudo attacks include pinned pieces, occupancy respected;
13 endgame king centrality: king centrality * (24-min(24,phase))/24, where phase is
both sides' N+B+2R+4Q count. Use integer numerator king centrality*(24-phase), no
fraction (a deployed weight can absorb /24). Features 8..10 pawn group,11..13 king/
phase group. Antisymmetric under color reflection, no learned intercept.

BCE of sigmoid(white score/400), labels1/.5/0 from game result, noisy not minimax.
R3 optimizer/float64/train-only RMS; equal-game observation weights for R4 fitting.
Regularize scaled coefficients toward handcrafted weights padded with zeros.
Lambda grid .0001,.001,.01,.1,1; validation equal-game BCE selects minimum, ties
larger lambda. Compare Handcrafted, strictly positive scalar calibration (train
BCE, bounded .01..10), frozen R3 model, refitted8, base+pawn, base+king, full14.
Calibration is a probability baseline, not a search-strength claim. All ablation
weights on absent groups fixed zero; optimizer and bounds/convergence retained.
R4.2 fits calibration/refitted8; R4.3 fits expanded groups; independent test remains
closed through all candidate/performance selection. No test-driven feature changes.

Candidate rule: lowest validation equal-game BCE among refitted8 and expanded
models with successful convergence, finite deployable weights, and static median
cost <=10x Handcrafted on frozen R2 positions. Ties prefer fewer active features.
At most one candidate for formal match. Freeze all weights, selection, metrics,
analysis code, model hashes and benchmark evidence before exclusive test marker.
One formal test operation evaluates all frozen baselines/ablations and paired
loss differences vs handcrafted/calibration/base and full vs each ablation.
Report 95% game-cluster percentile intervals, exploratory unadjusted multiple
comparisons explicitly, Brier and side/ply/material/result/window strata. Report
both equal-game and position metrics; do not claim temporal significance from
only two independent monthly windows. Candidate selection never uses test results.

## Formal performance and matches

Same clean binary/compiler, same unchanged search, QS/TT/PV=true, Hash16,
MoveOverhead10, single search thread, match concurrency1. Benchmarks: frozen R2
10 positions, depth3/4,3 repeats; static7 alternating repeats x100000 calls/model.
Record original8 vs expanded costs and nodes separately from strength.

Independent match openings: acquire at most 3 MiB /4000 PGNs from 2017-08 by same
bounded method, separate from model data. Without looking at results, sort accepted
games by SHA256(seed,gid), replay first12 plies, keep first200 unique canonical
positions absent from R3 opening set. No score/rating beyond data eligibility or
model-based filtering. Retain source and hashes, source-game IDs and FEN list.
If insufficient unique eligible positions, report partial; never repeat openings
as independent rounds. Freeze exact EPD/config before match.

Primary formal design: 200 distinct openings x swapped colors=400 games, fixed
sample, no interim selection/retuning/stopping. Mac fallback when Windows Ryzen
8940HX unreachable: tc1+0.01, maxmoves150, timeout10800 seconds, seed20261015,
no depth/node cap, no resign/draw adjudication except maxmoves. Expected ~20–40min
from R3 elapsed scaled by clock; run isolated from local builds/benchmarks. This
short clock limits external validity. Windows physical-host checks NOT_RUN unless
actually executed there. Hosted Windows CI is engineering evidence only.

Use existing fastchess PGN/parser/paired-round bootstrap (2000) and integrity
validator. Report W/D/L, five-bin pairs, natural/adjudicated/abnormal counts,
score and descriptive 95% paired bootstrap; transform p to 400log10(p/(1-p))
for Elo-equivalent point/interval (unbounded at endpoints). This is not SPRT and
not universal Elo. With200 pairs, worst-case SE<=.5/sqrt(200)=.0354; approximate
95% score half-width .0693 (~48 Elo at50%). Correlation/opening selection and
short clocks limit power; null/negative results valid. Retain all PGNs/logs,
identity, timing/nodes/NPS and exceptions; interrupted runs remain partial.

## Completion

Each verified stage committed/pushed and exact-SHA CI checked. Release CTest
before stage commit; Debug/ASan+UBSan for C++ changes/full acceptance, UCI and
fastchess compliance. Keep actual commands, revision/dirty state and failures in
VALIDATION.md / docs/validation/r4. Final report answers all eight objective
questions, links raw evidence, distinguishes facts, inferences, hypotheses,
PARTIAL/NOT_RUN/BLOCKED_ENV. Stop after R4; recommend but do not implement R5.

### Analysis detail sealed before any held-out evaluation

Five feature contrasts (refit8-calibration, pawn-refit8, king-refit8, full-pawn,
full-king) additionally receive 99% marginal game-bootstrap intervals (Bonferroni
five, nominal familywise >=95%). Primary 95% intervals remain descriptive;
99% intervals are only simultaneous for this specified five-contrast BCE family,
not all strata/metrics. The small number of windows and player dependence still
limit inferential claims. No feature or model outcome prompted this clarification.

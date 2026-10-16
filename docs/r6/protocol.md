# R6 Evaluation Target Alignment Study

Registered 2026-10-16 Asia/Singapore before acquisition/labels/training/matches.
The containing commit fixes this design. R3–R5 are sealed. No C++ search, feature,
model format or default evaluator change. Negative and inconclusive results count.

## Data and compute budget

Lichess CC0 standard rated 2018-01..04, each first 3 MiB compressed, at most 4000
complete games/48 MiB decompressed, through existing bounded_source/prepare.
Existing legal/Normal/rating>=1500/base>=180s/32ply filters and maximum eight
seeded positions/game at ply16..160, spacing7. Seed=20261016. 2018-01..03 use
80/20 game-hash train/validation; 2018-04 is future test. Retain whole games in
seeded hash order within caps 14000/3500/6500 positions (at most 24000 total).
Exclude R3–R5 source game/Site identities, retained positions and color mirrors,
and formal openings; remove any cross-split exact/mirror duplicates globally.
The ≤2000-position preflight is the first 256 selected TRAIN positions, never
used for model selection. Scale only after perspective/features/determinism pass.

Separate 2018-05 bounded prefix supplies 200 unique nonterminal 12ply openings,
selected by seeded game hash without scores. Exclude old sources/openings and
all R6 source games, retained positions and source-game 12ply positions. Training
also excludes these opening keys. No training/model selection on match openings.
PGN retains original game results/metadata; rows retain FEN, source, white-relative
14 features, game_result, teacher_evaluation, score perspective, budget/PV/counts.
Raw prefixes stay ignored; selected PGNs/JSONL/hash manifests allow reconstruction.
Monthly prefixes are convenience samples, not random month/population samples.

Teacher: official Stockfish **17.1**, Windows x86-64-avx2 release asset; save
release metadata, executable SHA256 and UCI identity. Threads=1, Hash=16 MiB,
MultiPV=1, Skill Level=20, UCI_LimitStrength=false, UCI_ShowWDL=true,
SyzygyPath empty, no tablebases. Every query starts a new game (cold hash),
`go nodes 20000`, no clock budget; retain actual final nodes/depth/PV/score/WDL.
At most four independent single-thread workers, never alongside performance
measurements/matches. Requested SF nodes may overshoot at engine check granularity.
Use final completed exact score, reject missing/bound/nonfinite scores. Convert
PovScore explicitly to white; also retain side-to-move score. Nonterminal dataset
only. Child terminal positions use exact python-chess outcome and are marked.
Mate is a separate signed field, never an ordinary cp measurement. Teacher soft
target sigmoid(clip(white_cp,-2000,2000)/400), mate win/loss 1/0, terminal 1/.5/0.
This fixed link is a modeling convention, not a Stockfish probability claim or
equality between SF normalized cp and UCL cp. Missing queries fail the stage;
resume completed labels by position identity without changing the budget.

Initial teacher cap about 500M nodes for data plus 200M for ranking; at most
2 hours labeling, 24 hours total formal matches, no paid compute. Preflight
records actual cost/coverage before final scale. Download cap 15 MiB game sources
plus one official teacher binary asset. No full evaluation database download.

## Training and validation-only selection

Reuse R4 NumPy/SciPy optimize: float64, train-only equal-game RMS, no centering,
zero intercept, BCE plus L2 toward padded Handcrafted, temperature400,
lambda=[.0001,.001,.01,.1,1], L-BFGS-B same tolerances. All models use identical
rows/features/splits and deployment format. G y=game_result; T y=teacher_target;
M y=alpha*teacher_target+(1-alpha)*game_result, alpha=.5,.8. Select lambda per
target by its own validation target BCE, larger lambda for exact ties. Losses
of different targets are not strength comparisons. Save all fits and weights.

Ranking uses first 128 validation and, after freeze, 128 test positions in
seeded position hash order. For EACH legal root move analyze the resulting child
independently with the identical cold-hash teacher budget, convert to root-mover
perspective. Static model scores on the same children use the same perspective.
This compares child static evaluation to child search, not root-score proxies.
Mate/terminal ordering uses signed100000 only as an ordering sentinel; cp MAE
excludes these. Primary is equal-game mean of per-position pairwise accuracy on
candidate pairs with teacher gap>=100cp, static ties count .5. Positions with no
qualifying pairs are disclosed/excluded from this metric. Report all-pair accuracy,
top-choice teacher regret, eligible pair counts and distributions. No scored
move pruning or favorable candidate selection. Candidate = best of T/M(.5)/M(.8)
on this PRIMARY validation metric; ties use teacher BCE then lexical name.
Retain G control and best M, and freeze candidate identity before test/matches.

Common metrics: equal-game game-result BCE/Brier, teacher-target BCE/Brier,
MAE/RMSE of clipped cp against clipped SF cp for nonmates, calibration bins
(mean prediction/teacher target/game result), phase0..8/9..16/17..24,
side-to-move and draws. Handcrafted/R4 Full14 are offline references on NEW data;
historical numbers untouched. Static cost/search throughput: same binary,
R2 ten positions, three seeded repeats depth4 and nodes50000, seven alternating
static blocks via existing benchmark. No speed gate for candidate selection.

Once selection, models, analysis and match schedule are committed, evaluate
independent test once; game-cluster bootstrap2000 seed20261016, descriptive95%
paired candidate-minus-G intervals for game BCE, teacher BCE/absolute cp error,
ranking primary. Other stratified/reference contrasts exploratory. Repeated
players and narrow time windows limit population interpretation. Test never
changes candidate, hyperparameters, clock, openings or match sample size.

## Actual playing strength

One clean current Windows Release MSVC binary for all engines, record full
revision/hash/build flags and actual evaluator identity. Existing pinned
fastchess v1.8.2-alpha/f618e345 reused with binary hash. Ryzen9 8940HX,
one match at a time, no concurrent heavy tasks. A→B→C→D fixed order:

| Group | First engine | Second | Budget |
|---|---|---|---|
| A | G | Handcrafted | 1+0.01s |
| B | frozen best T/M | Handcrafted | 1+0.01s |
| C | frozen best T/M | G | 1+0.01s |
| D | frozen best T/M | G | 50000 nodes/move; 1000+10s clock guard |

Each 200 same independent openings, two exchanged colors, 400 games, total1600.
Hash16, QS/TT/PV true, MoveOverhead10ms, maxmoves150, no score adjudication,
no SPRT. Record full PGN/UCI telemetry and W/D/L, paired score bins/95% interval,
termination categories, actual nodes/NPS/completed depth. Verify D actual go,
node counts, sufficient clock and classify mate/root draw/max-depth undershoots.
**C is the sole confirmatory strength contrast**, two-sided paired bootstrap95%
interval vs .5 (2000, same established floor/ceil quantiles); A/B/D exploratory.
No multiplicity adjustment needed for one claim; no confirmatory conclusions
from A/B/D. Elo equivalent400log10(p/(1-p)) conditional, not universal rating.
No pooling with historical hardware/compiler/results. No outcome-driven reruns,
extensions or tuning. Preserve completed games on failure; resume only missing
fixed schedule if required, disclose deviations. Formal per-group timeout6h.

## Delivery

One final report, this protocol, runnable pipeline/models and necessary raw
evidence. Rebuild data and models offline, target regression tests and existing
engineering checks. Commit/push actual results normally, inspect CI; do not
restore R5's removed state machine/audit wrappers. Handcrafted stays default.
Explain data/target/cost confounding relative to historical Full14; causal
mechanisms not isolated by this design remain hypotheses. Finish R6 and stop.

# R3 frozen research protocol (2026-10-15)

Scope: eight unchanged white-relative handcrafted-v1 features, zero intercept,
linear centipawn score and sigmoid(score / 400). The temperature is a scale
assumption, not an Elo calibration. Game results (1, .5, 0 from White) are noisy
long-term outcomes, not minimax position values. R1/R2 search remains unchanged.

## R3.1 data (defined before acquisition/training)

Source: https://database.lichess.org/standard/lichess_db_standard_rated_2017-01.pgn.zst
License: CC0, https://database.lichess.org/ (checked 2026-10-15).
Acquire only bytes 0–2097151 (2 MiB cap, HTTP Range), retain at most the first
3000 complete PGNs from that prefix. This convenience/time-ordered sample is
not representative of all Lichess or tournament chess; no seed shopping.
Preserve the exact selected source PGN compressed and all provenance hashes.

Keep standard, legal, completed games, normal Lichess termination (includes
resignation), distinct players, both ratings >=1500, base time >=180 seconds,
and at least 32 plies. Reject contradictions with forced final board outcomes.
Select at most eight nonterminal positions per game from plies 16..160 at
8-ply spacing, ordered by SHA-256(seed, game ID, ply). Seed=20261015.
Game identity hashes the initial FEN and full mainline moves; duplicate games
are excluded even if source IDs differ. Split by hashed game ID into 70/15/15
train/validation/test. Position identity uses FEN's first four fields (legal EP),
ignoring counters, canonicalized with its color-reflected mirror. Remove every
position shared across different splits, then retain one per identity globally.
Freeze test membership and data hashes before any model fit. No label-dependent
sampling or deduplication. Preserve filter counts and game/split manifests.

## R3.3 model selection (defined before training)

NumPy/SciPy float64 L-BFGS, deterministic zero-intercept fractional BCE via
logaddexp. Train-only RMS scaling (zero feature RMS -> 1). Optimize coefficients
in scaled score/400 space. Penalty: lambda/2 * ||beta-beta_handcrafted||²,
where beta = w * RMS / 400. Candidate lambdas: 0 (unregularized diagnostic),
0.0001, 0.001, 0.01, 0.1, 1. Select the positive lambda with smallest validation
BCE; ties prefer larger lambda. Initialize at handcrafted weights. Maxiter=1000,
gtol=1e-9, ftol=1e-12. Freeze chosen weights before a single official test pass.
Compare handcrafted, unregularized and selected regularized model on that pass.
Report BCE, Brier, counts, parameter changes, costs, side/phase diagnostics and
paired metric-difference bootstrap by whole game (2000 resamples, fixed seed).
No test-driven refitting. Retain failures and convergence diagnostics.

## R3.5 experiment budget (defined before model results)

Same clean R3 binary, Handcrafted vs frozen Linear model; QS/TT/PV enabled,
Hash=16, MoveOverhead=10, one search thread and match concurrency=1.
Existing frozen 10-position R2 suite: depths 3/4, three repeats, randomized
configuration order with seed=20261015. Inference microbenchmark separately.
Match: 16 unique standard opening positions, 16 swapped-color pairs / 32 games,
5+0.05 time control, no depth/node restriction, maxmoves=150, timeout=1200s,
seed=20261015, sequential openings. Only this one fixed sample is formal.
Use existing fastchess runner, integrity validator and round bootstrap; distinguish
natural endings, maxmove adjudication and failures. No Elo claim or SPRT, no
Windows experiment-host claim. Report raw artifacts and uncertainty even for a
negative result. No extra match or test-set tuning to seek a positive outcome.

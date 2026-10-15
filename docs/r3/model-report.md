# R3 model report (frozen before formal test)

Training code: `09335c08291f3a7f3c831372fda750903cef4ad5`, dirty=False.
Model SHA-256: `446d18379cfa66e018c4be56218db044339e4be137309c9a17dfbab69874269b`.

908 real Lichess CC0 games; 6039 positions (4208/990/841). Test: 124 games.
Source time-ordered convenience sample, normal endings only, ratings >=1500 and base >=180s. Outcome labels are noisy long-term results.

Selected positive lambda=0.0001 from validation BCE only. Tau=400, zero intercept, train-only RMS. All six candidate fits converged; total optimizer wall=0.007920s (excludes Python import/I/O).

| Feature | Handcrafted | Learned | Change |
|---|---:|---:|---:|
| pawn | 100 | 168.069513 | +68.069513 |
| knight | 320 | 279.334654 | -40.665346 |
| bishop | 330 | 279.976082 | -50.023918 |
| rook | 500 | 591.478089 | +91.478089 |
| queen | 900 | 1003.542749 | +103.542749 |
| pawn advancement | 5 | 6.003487 | +1.003487 |
| minor centrality | 4 | 24.938478 | +20.938478 |
| bishop pair | 30 | 116.017341 | +86.017341 |

| Lambda | Iterations | Train BCE | Validation BCE | Seconds |
|---:|---:|---:|---:|---:|
| 0 | 14 | 0.603343104 | 0.584510467 | 0.002285 |
| 0.0001 | 14 | 0.603343112 | 0.584510433 | 0.001451 |
| 0.001 | 14 | 0.603343898 | 0.584511176 | 0.001307 |
| 0.01 | 12 | 0.603401479 | 0.584587403 | 0.001130 |
| 0.1 | 11 | 0.604686694 | 0.585917760 | 0.001065 |
| 1 | 6 | 0.608297635 | 0.588765440 | 0.000683 |

## Single official test pass

| Model | BCE | Brier |
|---|---:|---:|
| handcrafted | 0.587908078 | 0.189141550 |
| unregularized | 0.583823172 | 0.188310734 |
| regularized | 0.583818366 | 0.188307783 |

Regularized minus handcrafted BCE: -0.004089712, game-cluster bootstrap 95% interval [-0.014669145945824394, 0.0070032892433522405]; Brier difference -0.000833767, interval [-0.005409751438487526, 0.0037535995949882716].
2000 resamples of 124 entire games, fixed seed. Both intervals include zero; no confident general improvement claim.

Early positions (ply <=40) and draw-labelled positions worsen. Later positions improve more; small draw stratum has only 47 positions. Both sides to move are represented (458 White, 383 Black). Raw stratum key `later_ply48_160` is a reporting-label error: its implemented predicate is ply >40 (first sampled ply 44); read it as ply41_160. This does not change any metric or selection.

A second train/validation-only fit in `.tools/r3-reproduce-v1` produced a byte-identical model. The official test was evaluated once after freeze; the retained exclusive test marker prevents accidental repetition. No test-driven refit or seed change.

Offline prediction error is separate from evaluation/search cost and playing strength. C++ deployment and controlled match remain to be completed.

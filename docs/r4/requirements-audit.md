# R4 completion audit

Scope: original user objective R4.1–R4.5; negative strength results are valid.
This maps acceptance to inspected evidence, rather than treating green tests as
proof of statistical validity. Final Git/CI closure is recorded in VALIDATION.md.

| Requirement | Evidence | Assessment |
|---|---|---|
| Frozen plan before acquisition, multi-date/month data, bounded cost | protocol4e1bb70;6x3MiB HTTP206 receipts, source PGNs | PASS; monthly prefixes remain biased within month |
| >=4000games/20000positions/6UTC dates | data manifest/diagnostics;6670/44681/6 | PASS |
| Legality/rating/time/player filters; game split; mirror dedup | source reconstruction,6670 distinct-player metadata, split/position IDs | PASS |
| Future test separation, overlap/opening/label/phase diagnostics | diagnostics.json;4 development/2 later windows;709/398/127 player overlap | PASS with explicit dependence limits |
| R1–R3 frozen data/models/raw evidence | base0d7a4f5 file comparison plus legacy validators | PASS |
| Raw hand, positive scalar, frozen R3, fresh8 baselines | selection;scale1.30727, originalR3 model hash, source correction retained | PASS |
| BCE/Brier, intervals, independent observational unit | equal-game weighted fit/loss;whole-game2000 bootstrap;window strata | PASS conditional; no independent-position or month-population claim |
| Feature groups, stable14 definition, C++/Python parity, symmetry/boundaries | protocol/architecture;r43-features/inference and randomized fixtures | PASS |
| Safe compatible deployment/UCI model switching | v1/v2 strict schema/hash/finite/size checks;UCI transactional tests | PASS |
| Train-only selection, group ablations, performance/model freeze before test | 20 converged fits,4clean benchmarks,freeze625d84e before exclusive marker | PASS |
| All model files reproducible | r43-reproduction.json, seven byte-identical files | PASS |
| One test evaluation, no test-led retuning | exclusive marker/testcode625d84e, unchanged model hashes through formal study | PASS |
| Same search/compiler/options; independent200 openings; fixed400 sample | source controls,build manifests,opening reconstruction,exact pair/order checks | PASS under recorded UCI-only recovery amendment |
| Single uninterrupted same-binary original execution | failed625d84e after60 pairs, preserved as failed | FAIL; disclosed, not relabeled PASS |
| Preserve completed outcomes and resume only unused sample | recovery plan before057f2cf continuation;120+280;no completed game repeated | PASS |
| Full PGN/log/nodes/NPS/terminations and paired effects | source hashes,final-stats/move coverage,study reconstruction,adjudications.json | PASS;391natural/9maxmoves/0abnormal completed games |
| Windows8940HX sustained physical host | no connected endpoint | NOT_RUN;Mac fallback performed |
| Elo improvement |35.875%,paired CI31.625..40.125%,Elo-equivalent−100.89 | FAIL in this setting;retain Handcrafted |
| All eight report questions, tables/figures/identity/commands/limits | final-report.md,artifact-index.json,plot scripts/lock,commands.md | PASS |
| Release/Debug/sanitizer/UCI/perft/regression/hosted CI | local logs and exact-SHA Actions snapshots | PASS for inspected code;latest archive CI checked at closure |
| Git stage commits/pushes, no R5 implementation | commit history/ROADMAP/VALIDATION;final clean state at closure | Final closure pending until archive CI confirmation |

The original failed run remains a failure. The recovered400-game study is the
preplanned sample with an explicitly documented protocol-only software repair,
not a claim that the original uninterrupted execution succeeded. No alternate
model, clock, sample size, opening or stopping criterion was selected after results.

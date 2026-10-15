# UCL working rules

- Before each task, read ROADMAP.md, relevant source and tests, and the latest
  VALIDATION.md entries and linked evidence. Check Git and CI state; verify the
  repository's actual state rather than relying on earlier chat summaries.
- Within the authorized milestone, autonomously complete implementation, tests,
  fixes, regression checks and Git commits, including authorized pushes and CI
  repairs. Infer routine choices; ask only for material gaps or new authorization.
- Follow ROADMAP.md for sequencing, not as authorization to start more work.
  Stop when the agreed acceptance criteria are met; do not start the next stage.
- Keep material progress, decisions, blockers and remaining steps in VALIDATION.md
  or linked repository notes, current during long tasks and before handoff or
  completion, so another session can resume without chat history.
- Keep research changes isolated and reversible. Commit each verified stage.
- C++20 owns engine/search/inference. Python owns data, experiments and analysis.
- Reuse chess-library for rules and legal moves; fastchess for matches.
- Keep Search, Evaluator and FeatureExtractor independent. Add abstractions only
  when a real implementation needs them; scope new algorithms/models to the
  authorized milestone and current ROADMAP.md.
- Evaluation is centipawns from the side to move. Features are white-relative.
- Test terminal positions before static evaluation. Never apply unvalidated moves.
- Run targeted tests, then `ctest --preset release` before a milestone commit.
- For each key validation, retain the tested revision (and dirty state), exact
  command, result and necessary logs/artifacts or CI links in repository records.
  Record failures and unrun checks; preserve earlier evidence when updating notes.
- Distinguish local test success, cross-platform CI success, target-hardware
  validation and measured playing-strength gains. Claim each only with matching
  evidence; a Windows CI pass does not validate the Windows experiment host.
- Never infer Elo improvement from smoke games. Record revision, parameters,
  seeds, binaries, hardware, raw artifacts and uncertainty for experiments.
- Keep generated builds, large datasets and model weights out of Git. Commit
  selected small experiment bundles explicitly with `git add -f` after review.
- macOS is the development host; Windows is the sustained experiment host.
- Keep interface details in ARCHITECTURE.md, experiment procedures in EXPERIMENTS.md
  and setup/run commands in README.md; update those documents instead of copying
  their detailed content here.

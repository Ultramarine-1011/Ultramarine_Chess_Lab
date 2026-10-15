# UCL working rules

- Finish authorized tasks end to end; infer routine choices from existing code.
- Keep research changes isolated and reversible. Commit each verified stage.
- C++20 owns engine/search/inference. Python owns data, experiments and analysis.
- Reuse chess-library for rules and legal moves; fastchess for matches.
- Keep Search, Evaluator and FeatureExtractor independent. Add abstractions only
  when a real implementation needs them. Do not add NN/RL systems in round one.
- Evaluation is centipawns from the side to move. Features are white-relative.
- Test terminal positions before static evaluation. Never apply unvalidated moves.
- Run targeted tests, then `ctest --preset release` before a milestone commit.
- Never infer Elo improvement from smoke games. Record revision, parameters,
  seeds, binaries, hardware, raw artifacts and uncertainty for experiments.
- Keep generated builds, large datasets and model weights out of Git. Commit
  selected small experiment bundles explicitly with `git add -f` after review.
- macOS is the development host; Windows is the sustained experiment host.
- Do not claim Windows success until the corresponding CI job has passed.

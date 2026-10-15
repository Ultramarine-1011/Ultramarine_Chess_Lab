# UCL working rules

- Complete the authorized work autonomously, including relevant fixes, tests,
  commits and authorized pushes. Ask only for material ambiguity or new authority.
- C++20 owns engine/search/inference; Python owns data/training/experiments.
  Reuse chess-library for legal moves and fastchess for matches.
- Scores are side-to-move centipawns; features are white-relative. Check terminal
  positions before static evaluation and apply only legal moves.
- Keep changes scoped. Run checks appropriate to changed behavior; use the full
  CTest suite for engine or experiment-system refactors. CI covers other platforms.
- Develop on train/validation data. Preserve independent test sets, historical
  results and useful raw evidence. Smoke games do not establish Elo gains.
- Keep generated builds, dependencies and large data out of Git. Save selected
  research bundles explicitly; ordinary exploratory failures need no permanent archive.
- README.md covers commands, ARCHITECTURE.md interfaces, EXPERIMENTS.md research
  methods, ROADMAP.md stage status. Update the relevant document only when needed.

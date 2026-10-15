# Selected experiment bundles

Generated runs are ignored. Keep `record.json`, `config.json`, `report.md`, raw
PGN, fastchess log and opening manifest together. Commit small selected bundles
with `git add -f experiments/results/<run>`; use release assets or external
storage for large data, with checksums and links in the record.

`smoke.json` compares the same binary under two names. It validates integration,
not playing strength. On Windows change engine paths to `build/release/ucl.exe`.

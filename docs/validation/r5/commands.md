# R5 command/evidence index

Working directory: `C:/Ultramarine_Chess_Lab/Ultramarine_Chess_Lab`.
PowerShell environment: `. ./.tools/windows-env.ps1` (standard VS/MSVC).
Python: `.venv/Scripts/python.exe`; all logs UTF-8. Stage state is VALIDATION.md.

| Command | Exit/result | Evidence |
|---|---|---|
| `python scripts/build_revision.py f933fe24ed983cb011b7a1bb0b9382c36a9b8d11` | 0, clean Original | original-build.json/log |
| `.tools/bin/fastchess.exe --help`, `--version` | 0 | fastchess-help.log, fastchess-version.log, tool.json |
| `python -m ucl.r5_study prepare` | 0 | configurations and preservation-before |
| `python -m ucl.r5_study preflight` (first) | 1, EPD absent before process start | experiments/results/r5-preflight-a/record.json |
| `python -m ucl.r5_study preflight` (v2) | 0, A/B/C/D actual runner | preflight.json and four r5-preflight-v2-* bundles |
| `python -m ucl.r5_openings acquire` | 0, 200 positions | r5-openings-v1/manifest.json and source |
| `python -m ucl.r5_openings validate` | 0, exact reconstruction | r51-openings-validate.log |
| `cmake --preset release -DPython3_EXECUTABLE=<root>/.venv/Scripts/python.exe -DCMAKE_PROJECT_INCLUDE=<root>/docs/validation/windows-init-20261015/windows-msvc-rules.cmake` | 0 | r51-configure.log |
| `cmake --build --preset release --parallel 4` | 0 | r51-build.log |
| `ctest --preset release` | 0, 6/6 | r51-ctest.log |
| full-length time smoke, same preflight A config with maxmoves=150, timeout=180 | 0, two natural games | r5-preflight-time-long bundle |
| `docs/validation/r5/capture-host.ps1 -Output <path>` | 0 | host-initial.json; thermal access denied retained |
| `git push origin main` preregistration | failed Schannel handshake | VALIDATION.md |
| `git -c http.sslBackend=openssl push origin main` | 0 | preregistration fcdfef0 on origin/main; process-only TLS backend |

Data acquisition/filter/exclusion implementation was uncommitted at acquisition;
its exact source is committed in R5.1 and offline reconstruction passed before
any formal result. Binary preflight always used the independently clean Original;
diagnostic runner dirty state is explicit. Formal identities are frozen later.

## R5.2–R5.5 completion

From recovery onward the working directory was
`C:/Ultramarine_Chess_Lab/r5-frozen-runner`. It reused the original venv and
standard Windows environment, with `PYTHONPATH=<worktree>/python` so the selected
checkout supplied the Python modules. No tools were reinstalled.

| Command / execution | Exit/result | Evidence |
|---|---|---|
| `python docs/validation/r5/profile-original.py` | 0, 210 component diagnostics | profile-original.json |
| `python scripts/build_revision.py 0cf58acacee5be9e5aee4385515caac2c3a8cb0c` | 0, independent clean Optimized | optimized-build.json/log |
| `python -m ucl.r5_equivalence --candidate .tools/engines/0cf58acacee5be9e5aee4385515caac2c3a8cb0c/ucl.exe --output experiments/results/r5-equivalence-clean-v1` | 0, PASS 48815 positions / 366 queries | r52-clean-equivalence.log; r5-equivalence-clean-v1/record.json |
| `python -m ucl.r5_performance run` at 97621be | 0, all measurements complete | r5-performance-v1/index.json and child benchmark-v1 bundles |
| `python -m ucl.r5_performance validate --output experiments/results/r5-performance-v1` | 0, summary reconstructed | existing archived performance package |
| `python -m ucl.r5_study matches` at d76ed2c | 1 after A400 completed, before B creation | r54-original-coordinator.log; r5-match-conditions-v1/index.json FAIL |
| `python docs/validation/r5/continue-frozen.py` at b065947 | 0, missing B/C/D400 each completed | recovery-plan.json; r5-match-conditions-continuation-v1/index.json PASS |
| `python -m ucl.r5_analysis --input experiments/results --output experiments/results/r5-analysis-v1` | 0, all1600 games / PGN-UCI correspondence / bootstrap | r5-analysis-v1/summary.json and A/B/C/D analysis/move files |
| Release configure/build with the original venv and local MSVC rules, then `ctest --preset release` | 0, 6/6, 39.56s after integrating 697737c | r55-integration-configure.log, r55-integration-build.log, r55-integration-ctest.log |
| `python -m ucl.r5_equivalence --candidate build/release/ucl.exe --output .tools/r5-simplified-equivalence` | 0, PASS 48815 / 366 for integrated engine | r55-simplified-equivalence.log; local ignored raw correctness bundle |
| `python -m unittest discover -s tests -p test_experiments.py` | 0, 15 tests | r55-node-label-tests.log |
| `analyze_group('B', ...); write_json(summary)` | 0, correct29 labels; WDL/bootstrap/moves/telemetry unchanged | r55-node-label-reanalysis.log; B/analysis.json |
| `python docs/r5/generate-report.py` | 0, generated from actual retained JSON | docs/r5/final-report.md |

The completed one-off continuation script is available in Git at b065947; it is
removed from current HEAD rather than retaining its obsolete source self-locks
as a live workflow. Its historical recovery plan and important FAIL/PASS records
remain. No A games or other completed formal games were rerun.

Current main's simplification APIs, schemas and dirty exploratory workflow are
preserved. The only R5 analysis compatibility extension accepts both an input
directory with A/B/C/D and the retained r5-match-*-v1 layout. A regression fix
classifies actual depth128 searches ahead of python-chess next-move draw claims;
this changes29 B labels, not outcomes or statistical methods.

## Commits and GitHub Actions

Every run below completed successfully with five jobs (macOS/Windows
Release/Debug and sanitizer); host research and CI remain distinct.

| Purpose | Full commit | Actions run |
|---|---|---|
| Preregister R5 | fcdfef0ff761ea97fcc35dbd7b364ed437454aa0 | docs only, skip-ci |
| R5.1 protocol / Windows / openings | 2bd311185f49e247abebcde2e40ed3adcc9d5d22 | [38770217890](https://github.com/Ultramarine-1011/Ultramarine_Chess_Lab/actions/runs/38770217890) |
| Preserve Windows evidence bytes | b339fa6b6794e9ce53d1a8d5dee65d759c99a7b5 | [38770570283](https://github.com/Ultramarine-1011/Ultramarine_Chess_Lab/actions/runs/38770570283) |
| R5.2 equivalent feature optimization | 0cf58acacee5be9e5aee4385515caac2c3a8cb0c | [38771077740](https://github.com/Ultramarine-1011/Ultramarine_Chess_Lab/actions/runs/38771077740) |
| Freeze performance/match identities | 97621be5b2b23ff6c71b1e5d22dfad2c3366cd91 | [38771839137](https://github.com/Ultramarine-1011/Ultramarine_Chess_Lab/actions/runs/38771839137) |
| R5.3 Windows performance results | d76ed2c28711e33d5a21dab5a8c840024eb00382 | [38772278198](https://github.com/Ultramarine-1011/Ultramarine_Chess_Lab/actions/runs/38772278198) |
| A400 preserved / missing-group recovery | b065947cf5c2682a5765c4ba344581028a0c82fa | [38775050500](https://github.com/Ultramarine-1011/Ultramarine_Chess_Lab/actions/runs/38775050500) |
| User's engineering simplification | 697737cdbed02f4bf0d29d00e5a15f62966b0f8c | [38774113323](https://github.com/Ultramarine-1011/Ultramarine_Chess_Lab/actions/runs/38774113323) |
| R5 completed results / analysis / integration | 8170f764a768fb2c3981e2bd75b25bf3ee98b676 | [38784569667](https://github.com/Ultramarine-1011/Ultramarine_Chess_Lab/actions/runs/38784569667) |

Completion commit8170f76 was fast-forwarded onto main and pushed; remote main
matched the full SHA above. Its five CI jobs all succeeded. Both local checkouts
were reconfigured/built clean at8170f76, and `ucl.exe --build-info` reported that
revision, dirty=false and the same MSVC Release flags. This final documentation
update only adds the verified delivery references; it changes no code or data.

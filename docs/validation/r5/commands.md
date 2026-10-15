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

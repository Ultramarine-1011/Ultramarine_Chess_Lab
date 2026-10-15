# 验证结果

工程简化，2026-10-16（Asia/Singapore）；基于 d76ed2c 的本提交工作树。
旧开发记录移至 [历史记录](docs/validation/history.md)。

| 检查 | 结果 |
|---|---|
| Windows MSVC Release configure/build；`ctest --preset release` | 6/6 通过 |
| 后续 Python 调整：`ctest --preset release -R 'experiments|research'` | 2/2，通过14项实验与19项研究测试 |
| 真实 fastchess 4局 smoke；match/benchmark 输出覆盖与 report | 通过 |
| dirty runner 调用干净历史 binary 的 `--formal` smoke | 通过；拒绝覆盖正式输出 |
| 16个 benchmark、12个 match 历史包离线验证 | 通过；另2个未完成包按预期拒绝 |
| `python -m ucl.r4_study` | 从原两批棋谱重建400局，统计与原结果一致 |
| `python -m ucl.r5_performance validate --output experiments/results/r5-performance-v1` | 已归档性能结果可重算，未重跑测量 |
| Skills quick_validate；当前文档链接；`git diff --check` | 通过 |

macOS/Windows Debug 与 sanitizer 由本提交的 GitHub Actions 验证，最终 CI 结果见
提交对应运行。所有 experiments/results 原始数据、R3/R4报告及历史协议未改动。
本轮只执行小型流程回归，未启动新的正式性能或棋力实验。

日常修改按范围选择测试；无需每次更新本文件或创建独立审计包。

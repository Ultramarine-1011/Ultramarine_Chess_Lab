# R1 验证记录（2026-10-15，Asia/Singapore）

本地引擎与实验验收基线：`fe3a23cfeeebade4e826ac8b2af2a96b34a06f50`。
双平台最终验收提交：`e603d431a721c3f883bb1843059d122ef6bd4de5`。
最终验收包含一项测试可移植性修正：使用显式 Windows/POSIX 路径覆盖空格参数，
避免把当前主机的路径分隔符写死在断言中。此后仅补充验收文档。

## 本地环境

macOS 26.7.1 / Apple Silicon，AppleClang 21.0.0.21000101，
CMake 4.4.4，Ninja 1.13.2，Python 3.14.5。
fastchess `alpha 1.8.2 20261011-ebfd64c`，完整提交见 third_party/README.md。

## 结果

| 验证 | 结果 |
|---|---|
| Release CTest | 5/5 通过 |
| Debug CTest | 5/5 通过 |
| ASan + UBSan CTest | 5/5 通过，无 sanitizer 诊断 |
| C++ 运行时检查 | 单元 27、搜索 23、Perft 14，共 64 项 |
| UCI 黑盒测试 | 6 个 unittest 通过 |
| Python 实验工具 | 5 个 unittest 通过 |
| fastchess UCI compliance | 40/40 步骤通过 |
| 干净提交 fastchess | 2 轮、4 局，候选 2 胜 0 和 2 负，无异常终局 |
| JSON Schema | 实验记录有效 |
| GitHub Actions 语法 | actionlint 1.7.12 通过 |
| 全新克隆 | 独立临时目录、全新 venv、锁定依赖安装、Release 构建和 5/5 CTest 通过 |
| GitHub 私有仓库克隆 | 从远程重新克隆到另一临时目录，全新 venv、构建和 5/5 CTest 通过 |
| Windows CI Release | MSVC 14.51，5/5 CTest 通过 |
| Windows CI Debug | MSVC 14.51，5/5 CTest 通过 |
| macOS CI Release/Debug | 两个构建分别 5/5 CTest 通过；Release fastchess 对弈通过 |
| macOS CI sanitizer | ASan/UBSan，5/5 CTest 通过 |

Perft 包括 startpos depth 4 = 197281、Kiwipete depth 3 = 97862、
残局 depth 4 = 43238、升变/易位局面 depth 3 = 9467 和 62379。
搜索分数在三种局面上与无剪枝的穷举 Minimax 对照一致。

选定结果：[`r1-smoke-20261015`](experiments/results/r1-smoke-20261015/report.md)，
同目录保存配置、完整记录、开局副本、PGN 与日志。
本次两个名称使用同一二进制，仅用于流程验证，不能推断 Elo。

双平台远程运行：[GitHub Actions #38693572181](https://github.com/Ultramarine-1011/Ultramarine_Chess_Lab/actions/runs/38693572181)，
5 个 job 全部 success。Windows 验证由 GitHub 托管 runner 执行；未在用户的
Windows 实验主机上测试硬件性能或长时间负载。

## 协作规范维护（2026-10-15）

- 范围：仅完善 AGENTS.md 的长期工作方式，并在此保留交接记录；未启动 R2。
- 版本：基于 `e6de4a06698f00989aed2472d22b9a1a2758a970` 的文档修改工作树；
  `build/release/ucl --build-info` 确认复用的 Release 产物来自该干净提交。
- 一致性检查：核对 ROADMAP.md、ARCHITECTURE.md、EXPERIMENTS.md、README.md、
  相关接口、搜索实现、测试与 CI 定义，无冲突；第一轮 NN/RL 限制改为按授权里程碑确定范围。
- 执行 `git diff --check`：通过；`ctest --preset release`：5/5 通过，
  覆盖 unit、search、perft、uci、experiments。
- 本次仅修改文档，不重跑跨平台 CI；上方 R1 CI 和目标硬件验证范围保持原有含义。
- 状态：本次维护完成，无阻塞；后续阶段等待明确授权。

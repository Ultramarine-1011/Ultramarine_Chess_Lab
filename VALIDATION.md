# R1 验证记录（2026-10-15，Asia/Singapore）

被验证的代码提交：`fe3a23cfeeebade4e826ac8b2af2a96b34a06f50`。
本文件及选定实验 bundle 随后的提交仅保存验收证据。

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

Perft 包括 startpos depth 4 = 197281、Kiwipete depth 3 = 97862、
残局 depth 4 = 43238、升变/易位局面 depth 3 = 9467 和 62379。
搜索分数在三种局面上与无剪枝的穷举 Minimax 对照一致。

选定结果：[`r1-smoke-20261015`](experiments/results/r1-smoke-20261015/report.md)，
同目录保存配置、完整记录、开局副本、PGN 与日志。
本次两个名称使用同一二进制，仅用于流程验证，不能推断 Elo。

Windows 本地未运行；远程 macOS/Windows 验证须以 GitHub Actions 实际运行结果为准。
当前 CI 定义包含两个平台的 Release/Debug，以及 macOS sanitizer 和 fastchess 冒烟对弈。

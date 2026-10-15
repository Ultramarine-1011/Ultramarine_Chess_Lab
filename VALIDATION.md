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

# R2 进行记录（2026-10-15，Asia/Singapore）

授权范围：搜索 QS → TT → PV ordering，各自独立开关/提交；实验完整性、固定
基准、R1/R2 小样本对照及本地/CI 验证。完成 R2 后停止，不启动 R3。
起点 `628bd24`，工作树干净；重新查询 R1 CI #38693572181，5 个 job success。
本地继续使用上方 Apple Silicon 工具链和 `.venv`，fastchess 固定版本不变。

## 实验完整性修复

- 测试版本：`628bd24` + 本阶段 dirty Python/schema/test 修改；C++ 复用 R1 二进制。
- 输入配置改存 `match-config.json`，保留 fastchess 自有 `config.json`。
- validate/report 实际检查每项产物大小/SHA-256、输入配置、引擎声明与编译版本、
  PGN 引擎/换色/起始局面/终局、结果文本与头部、从 PGN 重算的全部已存统计。
  增加每轮 0/0.5/1/1.5/2 分计数。R1 历史包保留原文件和统计格式兼容。
- `.venv/bin/python -m unittest discover -s tests -p test_experiments.py`：6/6 通过；
  包含配置覆盖模拟、逐个文件篡改、统计/种子/版本篡改、缺失 PGN、路径越界、
  即使重写 PGN 哈希后仍检测结果头部/正文矛盾。
- `.venv/bin/ucl-lab validate experiments/results/r1-smoke-20261015/record.json`：通过。
- `ctest --preset release`：5/5 通过（unit/search/perft/uci/experiments）。
- 初次新增测试失败：mock subprocess.check_output 意外影响 sysctl；已缩小到
  `--version` 调用后重跑通过。这是测试夹具问题，无引擎修改。
- 下一步：QS，随后 TT 和 PV；尚未声称 R2 性能或棋力收益。

## QS 阶段

- 测试版本：`b128e0a` + dirty QS/search/UCI/test 修改；新增 Quiescence 独立开关，
  默认启用。非将军搜索吃子（含 EP）与全部升变，将军搜索全部应对，无 stand pat。
  先终局/和棋判定，再静态评估；256 ply 安全上限中止迭代，保留上一完整结果。
- 命令：`cmake --preset release -DPython3_EXECUTABLE="$PWD/.venv/bin/python"`、
  `cmake --build --preset release --parallel 4`、`build/release/ucl_tests search`、
  `ctest --preset release`：搜索 33 checks；CTest 5/5 通过。
- 命令：`cmake --preset sanitize -DPython3_EXECUTABLE="$PWD/.venv/bin/python"`、
  `cmake --build --preset sanitize --parallel 4`、`build/sanitize/ucl_tests search`：通过。
- 新测试覆盖毒兵回吃、将军时安静应对、终局优先级、严格节点限制、中途 stop
  保留完整迭代及关闭 QS 的穷举 Minimax 对照。
- 首次搜索测试崩溃：新增夹具错误地让非行棋方已处于将军；Sanitizer/Debug
  断言定位到棋盘缺王。改用合法起始局面后 Release/Sanitizer 搜索测试通过。
  顺便移除脚本编辑带来的未用变量与重复计数赋值，编译无警告。

# R2 验收技术报告

引擎与实验代码：`eee9d44b5a73b36f06ae837e079a6afc66f8caaf`，测试/运行时工作树干净。
R1：`e603d431a721c3f883bb1843059d122ef6bd4de5`。二者分别从独立临时 Git worktree
以相同 AppleClang 21 / Release `-O3 -DNDEBUG` 编译；[构建清单](r2-build-manifest.json)
与 [R1 构建清单](r1-build-manifest.json) 保存实际二进制哈希、编译元信息和命令。

## 实现

- QS：吃子/EP/全部升变，将军时全部应对；终局优先、严格三次重复、50 步及中断。
- TT：固定内存、完整 Zobrist、深度/exact/lower/upper、最佳着法、代龄/深度替换、
  将杀 ply 归一化；分数复用校验半回合与可逆历史次数指纹。每次搜索新建。
- PV：上轮完整 PV 的合法路径前缀、TT 提示、原有吃子排序；全部 8 组合可消融。
- 实验：输入/fastchess 配置分离，产物哈希、PGN/终局/配对/统计重算、篡改回归；
  冻结基准、最终节点/微秒/TT 统计、历史版本构建及不同二进制身份保护。

关键独立提交：QS `1f5e0a0`、TT `d17b12f`、PV `53f7477`；实验修复 `b128e0a`，
基准/版本工具 `046d5b0`，UCI mate 分数转换修正 `eee9d44`。

## 验证证据

Apple A18 Pro / 6 逻辑 CPU / 8 GiB / macOS 26.7.1 / Python 3.14.5，详见
[环境](environment.json)。[Release](release.log)、[Debug](debug.log)、
[ASan/UBSan](sanitize.log) 各 5/5 CTest；C++ unit 27、search 685、perft 14 checks；
UCI 8、实验 Python 8 unittest。无 sanitizer 诊断。fastchess compliance 40/40，
[原始实验命令输出](experiment-commands.log)。

[双平台 CI #38700282364](https://github.com/Ultramarine-1011/Ultramarine_Chess_Lab/actions/runs/38700282364)：
macOS/Windows Release/Debug 和 macOS sanitizer 5 个 job 全部 success，
macOS Release 的 fastchess 冒烟也通过。这里的 Windows 是 GitHub runner。

## 性能、战术和对弈分别解读

固定 10 局面，每种配置 3 次；表中为各局面的重复中位数之和。
wall 包含 UCI 往返和每查询 TT 分配，短任务计时存在调度/温度噪声。

| depth 4 消融 | nodes | wall ms |
|---|---:|---:|
| 纯 Alpha-Beta | 91,000 | 14.64 |
| QS | 389,687 | 111.08 |
| QS + TT | 369,510 | 109.58 |
| QS + PV | 333,568 | 107.90 |
| QS + TT + PV | 266,968 | 93.59 |

同 QS 语义下，TT+PV 减少 31.49% 节点、这次测量少 15.75% wall 时间。
TT 单独启用不保证更快；表内是浅层、小型、特定硬件测量，不是普遍加速承诺。
完整 [720 查询消融表/原始数据](../r2-ablation-final-20261015/report.md) 另含 depth 1、
固定 10,000 节点、完成深度、NPS 和 TT 指标；depth 4 默认组合三次合计 TT hits
4,089、cutoffs 315。节点包含叶子、QS 和中断迭代；QS 不额外重复计数。

[跨版本 180 查询](../r1-r2-benchmark-final-20261015/report.md)：R1 与 R2-reference 的
60 组 depth 1/4 查询在分数、深度、节点、bestmove、PV 完全一致，
[可执行对照检查](check_reference.py) / [结果](reference-comparison.json)。
该批 depth 4 R1 为 91,000 nodes / 13.31ms，默认 R2 为 266,968 / 80.02ms：
QS 更宽的战术边界增加工作量，不能称为相同语义下的性能退化或加速。
六项自编战术检查在 depth 1 从 5/6 变成 6/6（修正毒兵回吃），depth 4 均 6/6。
这些标签只证明窄范围回归行为，不是经过标定的战术分数。

[16 局版本赛](../r1-r2-match-final-20261015/report.md)：8 个不同开局换色、depth 4、
30+0.1、单并发、seed=20261015、maxmoves=100。R2 13 胜 / 3 和 / 0 负，得分
90.625%；配对得分计数 [0,0,0,3,5]，按轮 bootstrap CI95 [81.25%,96.875%]。
15 局正常终局，1 局步数裁决。两个不同 SHA/二进制实际参与，PGN/strict 日志完整。
样本小、开局少、带步数裁决且同深度不同工作量；不能据此宣称 Elo 提升。
fastchess 原始日志自动输出的 Elo/LOS 不被本报告采纳。

## 限制与交付边界

TT 以 64 位键/历史指纹比较，存在通常的概率碰撞风险；保守路径检查与每次 run
清空限制命中率。TT 截断处 PV 可为合法前缀。256 ply 安全上限中止未完成迭代。
R1 缺少最终中断计数，跨版本只比较固定深度；高噪声短时 NPS 不代表棋力。

最初的 `046d5b0` 基准包保留作审计：R1 输棋 mate 的展示曾按步而非 ply 转换，
在上述最终包中已修正并回归测试，未改写旧证据。
Windows 实验主机持续负载和正式大样本棋力未运行，条件/命令在 EXPERIMENTS.md
已准备。本轮 R2 授权验收项目完成，停止，不启动 R3。

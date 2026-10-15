# 验证结果

工程简化验收，2026-10-16（Asia/Singapore），提交697737c。
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

工程简化的[GitHub Actions](https://github.com/Ultramarine-1011/Ultramarine_Chess_Lab/actions/runs/38774113323)
五项全部成功。该提交未改动既有experiments/results原始数据、R3/R4报告及历史协议。

日常修改按范围选择测试；无需每次更新本文件或创建独立审计包。

## R5 完成

按新的工程简化要求继续R5。已完成的性能与正式对照仍引用封存的
Original f933fe2 / Optimized 0cf58ac 二进制；本次工程整合没有替换在途引擎。
A/B/C/D各400局完成，全部PGN与完整UCI逐着对应，异常完整局为0。共享工作树简化期间A完成后旧协调器被dirty检查阻止，
已保留A全部400局与外层FAIL状态，b065947只续跑缺失B/C/D；未重跑A。
恢复事实见docs/validation/r5/recovery-plan.json和对应原始包，旧详细记录可从b065947读取。
后续交付保留697737c的新接口、精简文档和按范围验证，不恢复源码自锁或重复审计系统。

| 检查 | 结果 |
|---|---|
| Windows独立clean构建、开局离线重建与四组真实预检 | PASS；身份/日志见[命令索引](docs/validation/r5/commands.md) |
| 原版/优化版48815局面与366搜索查询 | PASS；特征、double、cp、move/PV与全部搜索计数精确一致 |
| 三次交替静态测量与450搜索查询 | PASS；静态159.4984→110.0119 ns/call，下降31.03% |
| 四组1600局及冻结身份、节点时钟限制 | PASS；原始包和逐着派生分析均归档 |
| 整合简化后Release configure/build及完整CTest | PASS，6/6，39.56秒 |
| 整合后引擎额外48815局面/366查询等价核验 | PASS；仅正确性，不作为当前HEAD新计时证据 |
| 深度128与可在下一着申和的停止原因回归 | PASS，15项实验测试；仅修正B组29项派生标签 |
| B组标签重算 | PASS；1604次mate、59次max_depth；胜负/区间/逐着记录/telemetry不变 |

[最终研究报告](docs/r5/final-report.md)给出四组W/D/L、配对区间、环境身份和限制。
D组55.125%，校正区间[50.625%,59.500%]，只支持优化相对原版的条件性收益；
C组37.25%，仍负于Handcrafted；B组47.50%，证据不确定。默认不变，未开展R6。
本研究计时仅对应封存版本；697737c另有推理校验简化，额外性能未在正式组中测量。
全部阶段提交及CI见命令索引。最终研究交付提交
`8170f764a768fb2c3981e2bd75b25bf3ee98b676`已推送main，
[对应GitHub Actions](https://github.com/Ultramarine-1011/Ultramarine_Chess_Lab/actions/runs/38784569667)
五项全部成功。主工作树和隔离工作树均已重新configure/build，实际build-info为该提交、
dirty=false、标准MSVC Release。随后仅补充本段与命令索引，不改代码或研究数据。

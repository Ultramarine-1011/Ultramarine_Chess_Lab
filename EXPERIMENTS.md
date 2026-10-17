# 实验方法

## 探索与正式研究

`ucl-lab match` / `benchmark` 默认是探索实验：允许未提交代码和 dirty binary，
保存实际 build-info、二进制哈希、参数、种子、主机信息、原始棋谱/测量和日志。
无需先提交或冻结源码。使用 `--overwrite` 可重跑未跟踪的探索输出；无用的临时
失败包可以清理。已跟踪历史包和正式包受保护。

`--formal` 增加二进制版本和比较条件检查。UCL binary 必须对应声明提交且其构建
源码干净；运行脚本所在工作树不必干净。`comparison=revision` 核对不同版本、
二进制与相同 compiler/build_type/flags；`ablation` 核对同一二进制、不同选项。
正式输出不覆盖。第三方引擎记录准确源码版本、构建说明和实际二进制哈希。
需要刷新 UCL build-info 时重新 configure/build。

研究结论保留足够复现的信息：代码版本、配置、模型、数据与划分、编译条件、
硬件、随机种子、原始结果和关键偏差。没有必要为每次探索保存源码自锁哈希、
全仓库快照、一次性启动标记或多份审计表。正式研究的重要失败与偏差需披露，
不要求永久保存无关的失败包。

## 配置与结果

现有最小例子为 `experiments/configs/smoke.json`。相对引擎/开局路径基于 `--root`
（默认当前目录）；config/output 基于命令工作目录。引擎名不同；games=2 自动
换色。rounds、seed、时控、并发、maxmoves、timeout 和可选 depth/nodes 显式配置。
`revision=HEAD` 解析当前提交，实际 UCL 编译版本另行采集。

原始输入、开局和模型随包保存。`record.json` 保存配置、测量/统计和产物哈希；
benchmark 不再另存同一份 measurements.json。日志可选详细 PGN/UCI telemetry，
压缩文件只做一次产物哈希。`report` 已调用 `validate`，无需连续执行两者。
验证检查文件完整性、合法棋谱、换色覆盖和重算统计；历史包仍可离线检查。

代码、配置和选定的小型研究包进入 Git；结果默认忽略，选定包用 `git add -f`。
大型数据/权重使用外部存储并保留来源、许可证和校验和。历史结论和重要原始证据
保持原样；原版本实现和重现命令可从对应 Git 提交取得。

## 统计与独立测试

- 同一开局交换颜色，按开局配对分析；记录样本量、停止规则和异常终局。
- 正式比较事先确定模型、开局、资源条件、样本量或有效的序贯检验规则。
  不按中途得分追加/截断样本，不挑有利种子，不混淆编译差异和算法收益。
- 当前工具报告 W/D/L、得分率、五档配对得分和 2000 次配对 bootstrap 描述区间。
  小样本/重复开局区间不能作为精确 Elo；CLI 没有 SPRT。
- 训练按棋局分组，避免跨集合重复/镜像泄漏。开发只用 train/validation；已有
  正式独立 test 不因工程简化而成为开发集。模型选择完成后才运行独立测试。
  已有 test-results.json 阻止重复正式评价和原目录重训；崩溃前的启动标记不再
  阻断重试。重新展示已完成结果应读取结果文件，无需重跑测试。
- 自然终局、外部裁决和异常终局分别报告。离线损失、静态推理耗时、搜索吞吐和
  实际棋力是不同结果；smoke、Perft、战术小样本不能证明 Elo 提升。

中断正式比赛时保留已完成数据，说明失败原因和修复范围，按原定开局/颜色安排
补齐缺失局。若环境或算法改变使结果不可合并，报告部分结果；无需通用审批状态机。

## 日常开发快测

`scripts/elo.py`直接复用`ucl.match.run_match`、`ucl.report`和bundle验证。
当前工作区增量Release对固定Stockfish17.1；可用`--stockfish PATH`明确选择其他
版本。默认目标`--sf-elo 1600`，启动时验证实际UCI身份、限强选项类型和数值范围；
配置`UCI_LimitStrength=true`、`UCI_Elo=N`、`Threads=1`、`Hash=16`。
不使用历史UCL基准，不修改通用版本比较工具。

第三方未知Git提交在引擎配置/记录中为`revision=null`，另记录实际UCI版本名、
`uci_id`、二进制SHA256和选项；不会继承运行器的UCL Git SHA。非空历史SHA与
UCL build-info仍按原规则验证，`code.revision`仍为运行器的完整Git SHA。

沿用`experiments/openings/elo-dev.epd`和相邻JSON的独立开发位置/构造/固定种子/哈希。
256个位置、每开局一轮换色、最多512局；默认64轮/128局、2+0.02、并发4。
不限制depth/nodes，maxmoves=150，异常终局由现有match拒绝并保留诊断。
限强Stockfish的bestmove可能不同于最优PV；日常配置`strict=false`仅容许该
已知PV首着不符告警，运行后及离线验证均拒绝其他告警。原有默认strict不变。

相对Elo为`400*log10(p/(1-p))`，配对bootstrap2000次的得分区间作单调变换；
粗略评级将同一差值和区间加上Stockfish目标Elo，不采用fastchess自动Elo/LOS。
全胜/全负差值为无穷；不足两轮或退化区间不提供有限粗略评级，区间边界保持无穷。
该评级只是Stockfish限强参考标尺，不等同于FIDE或Chess.com；实际限强表现随版本、
时控、开局及硬件变化，尤其短时控不能视为绝对标定。不能跨这些条件直接合并结果。
报告标明版本/二进制SHA、限强配置和时控，原始PGN与配置可重算。
`.tools/elo/`忽略且latest可覆盖；正式实验仍使用原保护规则和独立输出。

## 历史研究

[R3](docs/r3/protocol.md)、[R4](docs/r4/protocol.md)、[R5](docs/r5/protocol.md)
保存当时的研究设计与来源，不能拿后来的修改重写历史承诺。当前日常流程以本文
为准；历史研究数字见最终报告。R5四组各400局已完成，按开局换色对做2000次
bootstrap，预定四比较用名义98.75% Bonferroni区间；共享开局的组间差值仅作
探索性诊断，不作精确可加因果分解。结果与恢复偏差见[R5报告](docs/r5/final-report.md)。
正式数据使用封存Original/Optimized二进制；后续推理热路径简化的额外性能未测量。

[R6](docs/r6/protocol.md)固定同数据/特征/模型结构，比较棋局结果、教师和混合监督；
以validation合法候选子局面排序选模后才运行新的独立test。四组各400局中仅C
（混合监督对G，固定时间）为预定确认性棋力比较，其余组和事后C−D差值探索性。
补充validation推理/搜索成本在正式比赛结束后测量，未参与选模或比赛决策。
结果与局限见[R6报告](docs/r6/final-report.md)，不与历史原始比赛/计时合并。

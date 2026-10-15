# 实验规范

## 基本要求

每个实验必须记录完整代码提交、工作树是否干净、每个引擎的提交与二进制哈希、
编译器/编译选项、参数、种子、OS/CPU/内存/Python 版本、依赖版本及原始结果。
UCL `--build-info` 嵌入 configure 时的元信息；提交后必须重新 configure/build。
启用 `ucl_build_info` 的配置会核对二进制与声明版本，并拒绝正式运行 dirty 二进制。
第三方引擎手动填写完整提交与准确构建说明；其版本由实验者核实，哈希自动采集。

`schemas/experiment-v1.schema.json` 定义 v1 记录格式，状态为
running/completed/failed。工具保存 UTC ISO 8601 时间、命令行参数数组、
config、PGN、日志与各文件 SHA-256；输出目录只创建一次，失败也保留证据。
`--allow-dirty` 仅供诊断，记录会如实标记，不能作为正式算法改进结论。
终端/机器断电可能留下 running 记录；恢复后人工标注失败原因，保留原文件。

## 配置与运行

以 `experiments/configs/smoke.json` 为最小可运行示例。相对引擎及开局路径
相对于 `--root`（默认当前目录）；`--config` 和 `--output` 相对于命令工作目录。
两个引擎名称必须不同；`games` 固定为 2，fastchess 自动换色；并发、
时控、搜索深度/节点和最多步数均显式记录。
`revision=HEAD` 由运行器解析为当前完整提交；历史基线应填写其实际完整 SHA。
同二进制冒烟对弈不得作为算法比较。

可选 `openings` 配置：

```json
{"path": "experiments/openings/test.epd", "format": "epd", "order": "random"}
```

开局文件会复制进结果目录并计算哈希。`seed` 传给 fastchess 的 `-srand`，
同时用于报告 bootstrap。UCL 第一轮搜索确定性，不使用随机数。
内置 smoke 使用微型开局集，只用于合法走棋、时控和管道验收。
相同种子不能保证跨硬件时钟模式完全一致；固定 depth/nodes 更适合调试重放。

```sh
ucl-lab match --config experiments/configs/smoke.json \
  --output experiments/results/20261015-smoke-001 --fastchess .tools/bin/fastchess
ucl-lab validate experiments/results/20261015-smoke-001/record.json
ucl-lab report experiments/results/20261015-smoke-001/record.json
```

fastchess 由 `scripts/bootstrap_fastchess.py` 固定构建；安装脚本与
[官方 CLI 说明](https://github.com/Disservin/fastchess/blob/ebfd64cb7fac80d4822c50b07dca4fe934779d21/man.md)
为参数依据。日志启用 strict 模式，告警或引擎异常应使验证失败。

## 统计与比较

- 每次只改变一个研究因素。保留基线二进制、配置、提交和模型文件。
- 同一开局交换颜色，按完整轮配对分析；开局集合需有足够多样性。
- 报告 W/D/L、得分率、样本量、停止规则、异常终局与不确定性。
- 当前报告提供按换色轮重采样 2000 次的 percentile bootstrap 得分区间，
  仅作描述。极少样本或确定性重复局面可能产生退化区间，不代表精确棋力。
- smoke 与 maxmoves 截断结果只证明流程。正式比赛应事先设计时控、开局、
  adjudication 和样本量；不要将软件合法性测试解释为 Elo 进步。
- 长实验应预注册固定样本或 SPRT 假设及错误率，并采用合适的配对模型。
  当前 CLI 不实现 SPRT/显著性检验，不自动输出 Elo。
- 禁止删除失败记录、选取有利种子、混用不同编译参数却声称算法收益。

## R1 数据与训练预留（历史规范，现由 R3 落实）

TrainingSpec 预留 dataset_manifest、features、seed、target、split_manifest。
后续数据清单必须包括来源、许可证、SHA-256、位置/棋局数量和标签定义；
训练应按棋局划分，独立测试集冻结。模型清单记录特征版本、参数、训练环境、
离线指标和部署权重哈希，再经 fastchess 检验实战影响。

## GitHub 与存储

代码、配置、schema 和小型选定报告进入 Git。结果目录默认忽略；确认后使用
`git add -f experiments/results/<run>` 保存整个小型 bundle。
大型棋谱、数据和模型放 release assets 或外部存储，保留下载位置与哈希。
不要将 build、虚拟环境、可执行文件或原始大数据直接提交。
Mac/Windows 正式对比应记录硬件与线程差异；长负载优先 Windows 固定主机。

R2 起输入原样保存在 `match-config.json`；fastchess 生成的 `config.json` 独立留档。
`validate` 与 `report` 都检查产物大小/哈希并重新解析 PGN、核对全部已存统计、
换色配对和起始局面。它们可离线验证已归档的包，无需原主机二进制；二进制身份
在运行时通过 SHA-256 和 `--build-info` 核对。哈希用于发现意外篡改，不是数字签名，
不能识别同时恶意重写数据及全部元信息的行为。失败或 running 记录可供诊断，
但不会被 validate 判为已完成实验。旧 R1 包保留其实际原始文件。
## R2 固定搜索实验

`experiments/positions/r2-v1.json` 冻结 10 个合法局面（开局、中局、残局、毒兵、
将杀、安静升变、将军应对、EP、50 步边界和逼和）。六个局面带窄范围战术标签；
它们是自编回归检查，不是经过标定的战术能力量表。不得按测试结果删改冻结标签。

`r2-ablation.json` 预先固定 seed=20261015、3 次重复、depth 1 / depth 4 / nodes
10000，遍历 QS/TT/PV 全 8 组合。同一评估器、编译器、二进制、局面、Hash=16、
单搜索线程；只变算法开关。各查询 TT 冷启动，配置顺序按种子打乱，串行查询。
每次记录完成深度、分值、合法 PV、总 nodes、qnodes、内部微秒计时、NPS、TT
probes/hits/cutoffs/stores 和排序提示次数，以及含管道往返的 wall_ns。表中为各
局面重复测量中位数的和；raw 每查询数据仍在 measurements.json 和 record.json。
小于毫秒的计时噪声和 TT 每次分配成本会影响浅搜索；三次重复不代表性能显著性。
固定节点的节点数预算相同，但不同配置完成深度/PV/战术结果可以不同。

QS 改变边界，可能花更多节点而看见回吃；应分别比较相同 QS 语义下 TT/PV 的
性能，及相同资源下战术命中。默认组合与纯 Alpha-Beta 的同深度节点数并非相同
工作量。TT/排序可能在相同分值着法间改变选择，不要求 PV 文本完全相同。

R1 基线固定 `e603d431a721c3f883bb1843059d122ef6bd4de5`。按 README 的脚本
分别构建 R1/R2；基准额外包含全部开关关闭的 R2-reference，以核对 R1 语义。
版本赛预先固定 8 个不同开局、8 轮/16 局、换色、depth=4、30+0.1、并发 1、
seed=20261015、maxmoves=100；这是轻量流程/兼容验证，存在步数裁决，不能输出 Elo。
当前报告包括 W/D/L、得分率、五档配对得分计数和按轮 bootstrap 描述区间。

## Windows 持续实验准备（本轮不执行）

1. 在 VS Developer PowerShell 使用锁定依赖和同一工具链，按 README 分别构建
   两个完整提交，保留 manifest/build.log。使用同一个 fastchess 固定版本并记录哈希。
2. 固定物理主机、电源计划（高性能且接电）、散热/后台负载、单搜索线程、并发 1、
   Hash=16；记录 CPU/内存/OS/编译器/flags、时钟与电源计划，不能借用 Windows CI
   结果代替实验主机测量。先完整 Release CTest、UCI compliance 和短赛验证。
3. 正式长赛前另存冻结配置：例如固定 400 轮/800 局、10+0.1、移除 depth 限制，
   seed 固定，并用有来源/许可证/哈希且至少 400 个不同开局的文件换色配对。
   当前内置 8 开局不适合支撑大样本外推。预先记录资源、异常处理、maxmoves 和
   裁决规则；自然终局与步数裁决分开报告。不得看中途结果追加/提前截断样本。
4. 使用 comparison=revision 及完整 SHA；完成后 validate/report。保留全量 PGN、
   strict 日志和机器记录。异常终局使运行失败，修复后创建新目录，保留失败包。
   当前 bootstrap 是描述区间，不提供 SPRT 或显著性检验；如果要用 SPRT，应先
   单独设计并审阅其配对统计和错误率。本轮不声称 Windows 主机或大规模棋力已验证。

## R3 数据与线性评估协议

R3 预注册参数与有限预算见 [研究协议](docs/r3/protocol.md)。先冻结游戏分组及
跨集合局面去重后的测试清单，再训练；只按 validation 选择正则化，最终权重冻结后
一次正式 test 评估。棋局结果是带噪声的长期标签，不是精确局面价值。
fastchess 的 `Termination "normal"` 必须与棋盘自然结果一致；外部裁决
`adjudication` 单独统计，仍不能与强制终局矛盾。Lichess `Normal` 包含认输，
数据管线仅检查强制终局矛盾，不把它误当 fastchess 自然终局标记。

R3 正式冻结对比使用 `r3-benchmark.json` / `r3-match.json`：同一个 clean R3
Release binary，通过 UCI 切换 Handcrafted / 固定 hash Linear；QS/TT/PV=true、
Hash=16、MoveOverhead=10、并发1。预定义16个合法标准开局见 r3-v1.json/epd，
与训练结果无关的人工常用变例；每开局换色一次，共32局，5+0.05，无 depth/nodes
限制，maxmoves=150，1200s 超时、seed=20261015，不按比赛结果追加样本。
自然/裁决结果分开，模型原始文件与实际 evalinfo 一起留档。

benchmark-v1 可选 `static_evaluation=true`：额外对同一十局面用 C++ 各调用
Handcrafted/Linear 100000次、7轮交替顺序，保存 ns、checksum、模型哈希。
`validate` 复算 checksum、覆盖和汇总；`report` 独立显示静态耗时和搜索耗时。
同深度两种 evaluator 会产生不同树，节点差异不直接代表推理速度或棋力。

## R4 冻结研究

[R4协议](docs/r4/protocol.md)先于采集/训练封存。六个月窗口，前四月仅train/validation、
后两月独立时间test；每局总权重相同，整局bootstrap2000次。五个消融对比额外报告
99%边界，属于限定家族的名义Bonferroni控制；玩家与月份相关性限制仍保留。
所有模型先只在开发集拟合。固定R2局面逐组benchmark后，按validation BCE和
<=10倍静态成本门槛冻结唯一候选；由`r4_experiment freeze`保存选择/模型/成本/
分析代码/开局hash，随后一次独占test操作。禁止按test或比赛中途结果改模型。

独立2017-08 CC0源开局：12ply、按游戏身份hash排序去重、排除R3开局/R4源局；
固定200开局换色400局、1+0.01、Hash16、QS/TT/PV=true、并发1、maxmoves150。
Mac fallback预算约20–40分钟；Windows物理实验主机NOT_RUN，CI与物理主机分开。
保留PGN注释中的深度/节点/用时及完整log；自然/裁决/异常分列。Elo等效估计为
400log10(p/(1-p))，从配对得分区间变换，只适用于本设置；不是SPRT或总体定级。

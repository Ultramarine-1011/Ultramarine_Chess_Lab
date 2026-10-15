# R3：线性评估研究最终报告

日期：2026-10-15（Asia/Singapore）。R3.1–R3.5 工程与研究闭环通过验收。
默认仍使用 HandcraftedEvaluator；没有证据支持提升默认棋力。R4 未开始。

## 阶段与实现

| 阶段 | 完成内容 | 主要提交 |
|---|---|---|
| R3.1 | 恢复历史实验规范；修复自然终局校验；真实数据、过滤、游戏划分、去重与冻结 | `fcc652370c646ed6bfd37d0c308da4ab4c44a3ba` |
| R3.1 修正 | 训练前发现八 ply 采样只含白走，保留 v1，按七 ply 重新冻结 v2 | `1f512d491b0d8fa960e27b1d5e060aa5649235a1` |
| R3.2 | C++ 八维特征导出、Python 独立一致性检查、身份与输入哈希 | `e5b625fe70088935c6f3d41bf3e77f8ea574ccb1` |
| R3.3 | 正则化训练、validation 选择、模型冻结、一次正式 test | `09335c08291f3a7f3c831372fda750903cef4ad5` |
| R3.3 修复 | 固定跨平台 LF，恢复 Windows 原始字节哈希一致性 | `6113aef665c60e7d98caae793ad845711a8af082` |
| R3.4 | 严格模型加载、C++ 推理、UCI 切换、线程所有权和实际身份 | `96e41da2b1174252c93f309a02f3efe526860703` |
| R3.5 | 冻结对照、既有 benchmark 静态计时扩展、32 局比赛及完整性审计 | `476ceeee4b96d0ee1f2ffcf1f572f08833c4bf70` |

正式实验代码完整 SHA 为 **`476ceeee4b96d0ee1f2ffcf1f572f08833c4bf70`**。
同一 clean Release binary SHA-256：
`95bb42aaac9d770446f854e80d9562fc2bde89f88db2766aec0fb6a63986729e`。
后续归档/验收提交不改变这次实验的代码身份；全部提交见
[Git 历史](https://github.com/Ultramarine-1011/Ultramarine_Chess_Lab/commits/main)。

直接复用 C++ FeatureExtractor/Evaluator、Python TrainingSpec/Trainer、fastchess、
benchmark、validate、report。保留八维白方特征与原手工权重，零截距、颜色对称。
Search 与原 HandcraftedEvaluator 源文件相对 R3 起点完全相同，没有新增搜索优化。
LinearEvaluator 用 double 累加，按 half-away-from-zero 取整为当前行棋方 cp；
终局仍由 Search 先处理。UCI 默认 Handcrafted，先加载 SHA 与文件再切换 Linear；
失败明确报错并保留有效配置，成功切换先 stop/join，搜索捕获 shared_ptr。
部署文件为最大 4096 bytes 的固定 token Schema，严格 JSON manifest 单独保存
训练信息；固定 MIT PicoSHA2 验证原始文件 SHA-256，避免新增平台密码库依赖。

## 数据与无泄漏划分

来源：[Lichess 开放数据库](https://database.lichess.org/)，CC0-1.0。
从 `lichess_db_standard_rated_2017-01.pgn.zst` 仅获取 bytes 0–2097151，
HTTP 206；完整源文件 1,902,198,021 bytes，未下载完整大库。前3000个完整 PGN
作为固定方便样本。源前缀 SHA-256：
`d2eac0a6797bc104efc3ba2429073fd60905fdcc8e3b346fb4de82f6e69e091a`。

**实际时间窗口很窄**：原始 UTCDate/UTCTime 为 2016-12-31
23:00:00–23:16:53 UTC。月库名称不等于所取样本的 UTC 日期；不推测原因。
该样本不代表全月、全平台或职业棋局。正式冻结后未更换数据或随机种子。

保留标准初始局面、合法完整主线、不同玩家、双方 rating≥1500、base≥180秒、
至少32 ply 的 Normal 游戏。Lichess Normal 含认输，与 fastchess 自然终局语义
明确区分；拒绝与强制棋盘终局矛盾的标签。首轮过滤：970局 termination、629局
rating、400局时控、90局过短、2局畸形 rating、1局无效/未完成，保留908局。

| 集合 | 棋局 | 局面 |
|---|---:|---:|
| Train | 634 | 4,208 |
| Validation | 150 | 990 |
| Test | 124 | 841 |
| 总计 | 908 | 6,039 |

按初始 FEN+完整主线定义 game ID，seed=20261015，哈希分组70/15/15。
从 ply16..160 每7 ply 候选中确定性取最多8个非终局。忽略计数器的四字段 FEN
与颜色镜像共同定义位置身份；移除跨集合共享位置的全部2次出现，再去除集合内
1次重复。训练前冻结数据、划分和测试 ID。v1 八 ply 版本保留为缺陷历史证据，
从未训练；正式仅用 v2。6039行特征和原手工分数全部与独立 Python 实现精确一致。

白胜/和棋/黑胜标签为1/.5/0，是带噪声的长期结果，**不是 minimax value**。
原始选定 PGN gzip、过滤计数、许可/获取记录、HTTP headers、游戏清单与文件哈希：
[数据包](../../experiments/results/r3-data-v2/manifest.json)、
[特征包](../../experiments/results/r3-features-v2/manifest.json)。
原压缩前缀留于本机 .tools，可按 Range 重取；Git 保留可独立重建的选定源 PGN。
两种采样版本均已从源 PGN 重建，正式划分/特征输入哈希通过审计。

## 模型、选择与独立测试

模型 `v=w·x`，`p=sigmoid(v/400)`；400是固定标度假设，没有 Elo 校准含义。
NumPy2.5.4/SciPy1.18.1、float64、稳定 fractional BCE、L-BFGS-B、零截距。
RMS 仅拟合 train，无均值中心化，部署恢复原特征权重。
正则为 `λ/2 ||β−β_handcrafted||²`，其中 `β=w*train_RMS/400`。
固定候选0/.0001/.001/.01/.1/1，validation BCE选正则λ=.0001；0仅作未正则对照。
6个候选全部收敛，总优化器时间0.007920秒（不含解释器导入、I/O及完整流程成本）。
精确配置、每候选时间/迭代/梯度/环境均保留；train+validation-only 第二次拟合
生成字节完全一致的模型。没有根据 test 再训练。

| 特征 | 原手工 | 学得权重 |
|---|---:|---:|
| Pawn | 100 | 168.069513 |
| Knight | 320 | 279.334654 |
| Bishop | 330 | 279.976082 |
| Rook | 500 | 591.478089 |
| Queen | 900 | 1003.542749 |
| Pawn advancement | 5 | 6.003487 |
| Minor centrality | 4 | 24.938478 |
| Bishop pair | 30 | 116.017341 |

冻结模型 SHA-256：
**`446d18379cfa66e018c4be56218db044339e4be137309c9a17dfbab69874269b`**。
[模型清单](../../experiments/results/r3-model-v1/model-manifest.json)、
[训练选择](../../experiments/results/r3-model-v1/selection.json)、
[一次正式测试](../../experiments/results/r3-model-v1/test-results.json)、
[完整离线分析](model-report.md)。独占 test marker 保存冻结模型身份并防止误重跑。

| Test，841局面/124局 | BCE | Brier |
|---|---:|---:|
| Handcrafted | 0.587908078 | 0.189141550 |
| Unregularized | 0.583823172 | 0.188310734 |
| Regularized | 0.583818366 | 0.188307783 |

正则模型减手工：BCE −0.004089712，按完整棋局重采样2000次的95%区间
[−0.014669146, +0.007003289]；Brier −0.000833767，区间
[−0.005409751, +0.003753600]。均跨零，不能宣称总体预测改善。
两种走棋方都覆盖（test白走458/黑走383）；早期局面和和棋标签分层反而退步，
和棋仅47局面，结果很不稳定。原 test 文件的 later_ply48_160 是标签文字错误，
实际 predicate>40、首采样ply44；报告按真实谓词解释，未改写/重算正式测试。

## 推理、搜索和比赛分别解释

本地 Apple A18 Pro / arm64、6 logical CPU、8 GiB、macOS26.7.1，AC接电。
AppleClang21.0.0.21000101，Release `-O3 -DNDEBUG`。实际硬件/电源/负载记录
随包保留；没有控制全部桌面后台活动，短时计时只作描述，不推断显著性。

同一binary，Hash16、QS/TT/PV=true、MoveOverhead10、一个搜索线程。
固定原十局面，depth3/4各三次重复，合计120查询，配置顺序按固定种子打乱。

| 配置 | 深度 | 节点（逐局面中位数之和） | Wall ms（同口径） |
|---|---:|---:|---:|
| Handcrafted | 3 | 82,410 | 29.402 |
| Linear | 3 | 134,403 | 42.475 |
| Handcrafted | 4 | 266,968 | 76.153 |
| Linear | 4 | 287,201 | 81.245 |

两者各深度的窄范围战术检查均6/6；不解释为标定的战术水平或棋力。
depth4 Linear节点多7.58%、wall多6.69%。Evaluator改变了树，节点差异不能
直接解释成推理速度。另以相同FEN各调用100000次、7轮交替顺序的静态测量：
Handcrafted23.016ns/call，Linear24.300ns/call，约多5.58%。这是逐局面中位数
的平均；原始时间、checksum与UCI transcripts均保留。
[完整 benchmark 包](../../experiments/results/r3-benchmark-final-20261015/report.md)。

正式 match：16个事先冻结的不同标准开局，各交换颜色，共32局；5+0.05、
无 depth/nodes 限制、并发1、maxmoves150、seed20261015、1200秒超时。
实际仅运行这一批，2026-10-15 17:19:52–17:27:04（Asia/Singapore），约7分11秒。

| Linear 对 Handcrafted | 结果 |
|---|---:|
| 胜/和/负 | 12 / 5 / 15 |
| 得分率 | 45.3125% |
| 独立换色轮 | 16 |
| 配对五档计数 | [4,1,7,2,2] |
| 配对 bootstrap CI95 | [28.125%,60.9375%] |
| 自然终局/外部裁决/异常 | 32 / 0 / 0 |

16个指定开局均恰好覆盖2局，配对、结果与终局状态全部通过审计。
[完整 match 包](../../experiments/results/r3-match-final-20261015/report.md)。
**没有证据证明棋力提升，也不足以断言可靠退步**。fastchess原始日志自动输出的
Elo/LOS不作为本研究结论。未追加对局、改种子、改权重或按中途结果停止。

离线结果的小幅误差下降没有转化为这一设置下的正向比赛结果。可能原因包括
八维表示有限、长期结果标签噪声、时间/玩家/局面分布过窄、偏重中心性与双象、
早期/和棋预测退步、线性权重与搜索树的交互及推理开销。它们是解释假设，
不是已被消融实验确认的因果结论；本轮没有为寻找正结果继续调参或追加比赛。

## 工程证据、缺陷与限制

本地 Release/Debug/ASan+UBSan各6/6 CTest；最新clean实验代码再跑Release6/6。
包含原unit/search/perft、真实管道UCI10测试、Python实验8测试、research10测试；
fastchess compliance40/40。全部6039局面Python/C++推理误差<1e-9cp，取整完全一致。
所有保留的历史R1/R2正式包与R3包validate/report复核；最终审计见
[审计记录](../validation/r3/r35-final-audit.json)，原始日志和精确命令见
[验证目录](../validation/r3/commands.md)与[总记录](../../VALIDATION.md)。

跨平台对应精确SHA的Actions（macOS/Windows Release/Debug、macOS sanitizer，
Mac Release另含fastchess smoke）五项通过：
[R3.4](https://github.com/Ultramarine-1011/Ultramarine_Chess_Lab/actions/runs/38711662455)、
[正式实验代码](https://github.com/Ultramarine-1011/Ultramarine_Chess_Lab/actions/runs/38711949849)。
最终归档提交的独立CI状态另在VALIDATION末尾记录，不能替换正式实验SHA。

真实修复：历史EXPERIMENTS覆盖回归、自然终局误接受、八ply采样走棋方混叠、
Windows CRLF导致哈希失效、分层标签文字，以及数值依赖要求Python≥3.12
而原项目仍声明3.11的安装契约不一致（已同步pyproject/CMake/README）。保留失败的CI/测试日志与采样v1。
中间一次文档提前误写CI全通过已更正；Windows失败、修复与成功run均留档。
所有源代码/配置/选定小型正式产物入Git，大数据前缀及二进制仅留本机.tools。

未运行Windows持续实验主机、长赛/SPRT、广泛数据/开局外推、独立测试集的第二轮
模型选择或R4算法。Hosted Windows CI只验证工程，不等于用户Windows主机验收。
按棋局聚类的区间也未建模玩家/短时间窗口间相关性；不作跨总体的强结论。

## 验收与下一步建议

R3工程与研究验收通过：真实数据到冻结模型、独立测试、C++部署、受控对弈和
可复核统计闭环完整；可靠的不确定/非正向结果被如实保留。没有达到棋力提升的
证据门槛，继续保留Handcrafted默认。所有实施范围限于R3。

R4需重新授权。建议先获取跨日期、更广泛且独立的棋局/开局与足够预算，预定义
标签质量和局面分布诊断，再判断是否值得扩展特征或模型；不应由此次小样本
直接推进更复杂搜索或模型。当前没有启动任何R4开发或长时间Windows任务。

# 架构与接口

## 边界

```text
GUI / fastchess
      │ UCI stdin/stdout
      ▼
UCI session ──► Search ──► Evaluator ──► FeatureExtractor
                  │            │              │
                  └──────── chess::Board ─────┘

Python CLI ──► fastchess 子进程 ──► 两个独立引擎进程
      └────► config + record JSON + PGN + logs + Markdown report
```

规则、位棋盘、合法走法、易位、吃过路兵、升变、Zobrist 和棋谱历史来自
Disservin/chess-library。UCL 独立实现搜索与评估，不维护另一套规则。
库固定至提交，原样保存头文件与许可证；无网络也能构建 C++ 引擎。

## C++ 公共接口

| 接口 | 输入 → 输出 | 约定 |
|---|---|---|
| `FeatureExtractor::extract` | `const Board&` → `vector<float>` | 白方视角；名称包括特征版本；顺序固定 |
| `Evaluator::evaluate` | `const Board&` → `int` | 当前行棋方视角的厘兵分值；不处理终局 |
| `Search::run` | 棋盘副本、评估器、限制、stop_token、回调 → SearchResult | 不修改调用方；保留历史；结果含合法着法、PV、分数、完成深度、节点、耗时 |

Evaluator 不强制依赖 FeatureExtractor：手工/线性评估可用特征；未来 NN
可自行管理输入张量。Search 只依赖 Evaluator，MCTS 可另行实现同一接口；
若 MCTS 需要 policy/value，届时再增加最小的专用接口，不提前塞入 Alpha-Beta。
调用方负责让特征器比评估器活得久，评估器比搜索活得久。当前仅单搜索线程。

## R1 算法（保留的历史基线）

迭代加深、fail-soft Negamax/Alpha-Beta，稳定的吃子/升变排序。没有 TT、
静态搜索、空着剪枝、LMR 或并行搜索，因此存在典型的水平线效应，棋力尚未标定。
每个节点先生成合法走法，检查将死/逼和，再检查 50 步、三次重复、子力不足；
最后才做深度截断评估。搜索采用严格三次重复计数，历史通过 UCI moves 重放保留。
FEN 本身不能恢复此前的重复历史。

将杀基准 30000，随 ply 调整以偏好更短的杀棋；静态分值被限制在将杀区间外。
超时/节点耗尽/stop 时，仅采用最后完整迭代；若未完成一层，返回合法的首着兜底。
节点数按进入搜索节点累计，包含根节点及叶节点，迭代间不清零。
Perft 独立于评估与搜索，不应用和棋截断。

手工特征 v1 为 8 维：兵、马、象、车、后的子力数量差，兵推进量差，
轻子中心性差，双象指示差；权重为 `[100,320,330,500,900,5,4,30]`。
此基线可整体替换，无模型文件或训练依赖。

## UCI 与时间控制

主线程读取命令，`std::jthread` 执行搜索；输出通过互斥锁逐行发送。
`stop`、新 position、ucinewgame、quit 和 EOF 均请求停止并 join。
每次搜索使用独立棋盘副本；position 解析先验证 FEN 和全部合法着法，成功后再替换。
畸形命令输出 `info string`，保留会话。FEN 限于标准棋，半回合计数接受 0–100，
全回合计数接受 1–32767；不把 FEN 语法验证声称为完整可达性证明。

`movetime` 扣除 MoveOverhead；时钟模式按 `remaining/movestogo + increment/2`
分配，默认 movestogo=30，且不超过扣除余量后的剩余时间。每节点检查停止条件；
操作系统调度和当前节点处理带来少量实际超时，应在正式对弈时保留合理余量。
`go infinite` 等待 stop 才发布 bestmove；其他组合限制由先到者终止。

## Python 与实验产物

`records.py` 收集元信息并原子写 JSON；`match.py` 验证配置、解析路径、
计算哈希、调用 fastchess 并记录失败；`report.py` 校验 PGN 和换色配对，
输出 W/D/L、得分率与按轮重采样的 bootstrap 区间。
`training.py` 复用 TrainingSpec/Trainer 边界，提供版本化数据输入、正则线性
训练、validation 选择和冻结模型后的独立测试。依赖由 pyproject.toml 声明，requirements.lock 固定实际版本。

## 验证层次

1. 单测覆盖特征、分数符号、位置解析及特殊走法。
2. Perft 使用 startpos、Kiwipete 及升变/易位/吃过路兵测试局面。
3. 搜索测试覆盖替换评估器、将死/逼和/重复/50 步、PV、预算和确定性。
4. UCI 使用真实管道和独立 python-chess 客户端校验合法着法、停止与时钟。
5. Python 测试覆盖 schema、原子写入、参数边界、PGN 和失败留档。
6. macOS/Windows Release/Debug CI；macOS ASan/UBSan；macOS fastchess 冒烟对弈。

## R2 搜索增量

`SearchOptions::quiescence` / UCI `Quiescence` 默认 true，可关闭以还原 R1 截断。
QS 复用同一 Negamax 与停止/终局逻辑。非将军以静态分为 stand pat，仅扩展吃子和
所有升变；将军扩展所有合法应对。每次进入节点计一次，qnodes 是总 nodes 的子集，
包含深度 0 节点。主搜索深度仍上限 128，含 QS 的绝对 ply 上限 256；触顶中止
整个未完成迭代，不把将军中的静态分当结果。QS 改变深度边界语义，因此同深度分数、
PV 长度和节点数不要求等于关闭 QS 的搜索。

TT 使用 chess-library 的 Zobrist 主键，直接映射固定内存（默认 16 MiB，UCI Hash
1–1024），同一迭代优先保留深项，下一迭代允许替换旧项。缓存深度、exact/lower/upper、
最佳着法及 ply 归一化将杀分数。只缓存主搜索，QS 不缓存；探测前仍先检查终局。
分数截断要求完整主键、相同剩余深度、相同半回合计数、相同可逆历史指纹，以及
缓存着法在当前合法走法中。更深项不替代浅层语义；根不直接截断。PV 可在 TT
命中处结束，为合法前缀，不伪造未搜索延续。

历史指纹按可逆路径经过的局面哈希做可交换累加，表示重复所需的出现次数，
兵步/吃子后清零。root 已有历史不公开，作为整次 run 的固定不透明前缀；TT 只在
一次 run 的迭代间复用，不跨 go/评估器/选项/ucinewgame。由此不会在不同 root
历史间混用分数。半回合计数另存，避免 50 步边界串用。哈希和历史指纹均为 64 位，
存在通常的概率碰撞风险。此保守方案比忽略路径的 TT 命中率低，以正确性为先。
`UseTT=false` 完全不分配和探测 TT；qnodes、TT probes/hits/cutoffs/stores 独立计数。

`PVOrdering=true` 独立启用上一完整迭代的 PV 和 TT 最佳着法排序：仅在路径仍匹配
旧 PV 前缀时采用该 ply 的 PV 提示，其次 TT 提示，再复用稳定吃子/升变排序。
提示仅与已生成的合法走法比较，绝不直接应用缓存着法。关闭 TT 时旧 PV 排序仍工作；
关闭 PVOrdering 时 TT 仍可复用分数。排序不引入 PVS、LMR、空着或并行算法。


## 基准和版本身份

UCI 在 bestmove 前输出 `info string ucl_stats {JSON}`：最终实际 nodes、qnodes、
完成深度、厘兵分、微秒计时及 TT/排序计数，包含中断迭代的工作量。普通 info depth
仍只表示完整迭代。`benchmark.py` 通过独立 python-chess 客户端检查着法/PV，保存
输入、局面集、每查询原始测量和完整 UCI transcript；按局面取重复测量中位数。
benchmark-v1 与 match experiment-v1 分别有 Schema，validate 都检查文件哈希和
统计重算。R1 没有最终中断统计，固定节点下仅能报告其最后完整迭代，不能把它与
R2 最终节点数直接相比；跨版本采用固定深度。

`build_revision.py` 从完整 SHA 创建临时 detached Git worktree，以同一 Release
参数编译，保留 binary/build.log/manifest 后移除临时 checkout。manifest 记录
命令、二进制哈希和嵌入版本。`prepare_comparison.py` 据两个 manifest 生成跨版本
配对赛和基准配置。comparison=revision 要求不同 SHA、不同 binary hash、干净
UCL provenance、相同 compiler/build_type/flags；comparison=ablation 要求同一
二进制、不同显式选项。smoke 允许同二进制。身份核对和合法选项检查失败会留档。

## R3 特征数据边界

`ucl --features` 从 stdin 每行读取一个经过既有 position parser 校验的 FEN，
每行输出 feature_version、八维白方 features 和 side-to-move handcrafted_cp。
非法输入使进程明确失败，防止行错位。Python `feature_data.extract` 调用同一
C++ extractor，并用独立 python-chess 特征实现逐行精确交叉检查；训练输入
始终采用 C++ 输出。`export_dataset` 保留局面/游戏 ID、split、label、FEN、
特征版本和导出 binary/build provenance。handcrafted-v1 的定义和顺序不变。

## R3 训练与模型格式

`LinearTrainer` 实现既有 `Trainer.fit(TrainingSpec, output_directory)`，用 C++
特征、train-only RMS、零截距 fractional BCE 和以手工 beta 为中心的 L2。
模型选择只访问 train/validation；`evaluate_frozen` 在模型文件和选择记录已哈希
冻结后，用独占 marker 限制正式 test 步骤。来源、环境和严格 JSON manifest 的
契约为 `schemas/linear-model-v1.schema.json`。

部署文件为轻量 ASCII `ucl-linear-v1` 固定顺序 token Schema：
`features handcrafted-v1; perspective white; temperature 400; intercept 0;`
`weights 8 <八个有限 double，绝对值<=10000>; dataset_sha256 <64 hex>;`
`split_sha256 <64 hex>; end`（各字段用换行分隔，实际示例见正式 model.txt）。
完整文件最大 4096 bytes，拒绝多余字段/错误版本/维数/数值；调用方提供完整
SHA-256，加载前核对文件字节。温度只用于训练概率，部署直接算原空间 w·x，
按 lround 的 half-away-from-zero 取整并转换当前行棋方符号。

## R3 Evaluator 部署与运行身份

`LinearEvaluator::load` 验证最大文件长度、完整 SHA-256、固定 token Schema、
八维 finite double 及范围、特征版本和来源哈希；SHA 使用固定 MIT PicoSHA2。
每次 evaluate 直接调用原 FeatureExtractor，累加 double 后按当前行棋方转换。
终局依然由未改动的 Search 优先处理，TT 每次 run 冷启动。

默认 UCI Evaluator=Handcrafted。加载顺序为 ModelSHA256 → ModelFile →
Evaluator=Linear；没有有效模型时拒绝切换。新模型先完全验证，成功后 stop/join
再替换；失败保留有效 evaluator/model。搜索捕获 shared_ptr<const Evaluator>，
特征器在会话全程存活；任何有效 evaluator/model 切换都会停止并 join 原搜索。
`evalinfo` 返回实际 evaluator 和 model_sha256；`eval` 附加当前静态评分。
`--infer <file> <sha>` 批量返回未取整 white_score 和 side-to-move cp。
`--eval-benchmark <file> <sha>` 每个 FEN 做 7 次交替顺序、每模型 100000 次
静态调用，保留 checksum 与原始 ns；不涉及搜索和棋力解释。

match/benchmark 复用统一选项排序和加载检查，实际 UCI probe 核对配置，
记录可选 `engines[].evaluation`，保持旧包兼容。正式包复制模型原始文件，
validate 检查 evaluator 配置、实际 hash 和保留模型，拒绝伪装加载/丢失身份。

## R4 数据与校准研究边界

`r4_data`复用R3合法PGN、game ID、七ply采样与镜像去重；新增可选split resolver
和元数据，默认路径严格保留R3输出。六个月分源Range、原始PGN与合成来源header
分别保存，未来两源为test；重建验证包括全部文件和诊断。特征导出按数据kind分派
验证，不改变原八维接口。`r4_training`复用Trainer的数值目标函数并添加可选观测
权重；每局总权重相同，R3默认无权路径不变。fit仅计算train/validation指标，
正尺度校准及八维重拟合冻结后等待R4.3消融/性能选择，独立test仍关闭。

## R4 可解释特征与部署

`InterpretableFeatures`固定名称`interpretable-v2`，14维，前8维精确复用v1；
后六维依序是孤兵数、叠兵额外数、通路兵推进量、兵盾数、受攻击王环格数、
残局国王中心性整数分子。定义见冻结协议；全部白减黑、颜色镜像反号。
王环使用chess-library伪攻击（含被牵制棋子），通过python-chess独立参考逐行核对。
phase=min(24,N+B+2R+4Q两方总计)，末维=中心性差*(24-phase)，避免分数误差。
升变额外子力按24截断。王盾为同/邻文件一或二格前方的兵，与是否易位无关。

`--features-v2`是独立导出入口；`--features`八维字节语义不变。新部署格式
`ucl-linear-v2 / features interpretable-v2 / weights 14 ...`，其余固定token和
4096字节、有限值/范围/sha256限制与v1相同。加载器按严格版本/维数选择静态生命周期
特征器，v1仍使用调用方原特征器；任何混合格式拒绝。UCI选项保持Evaluator=Linear，
实际identity分别linear-v1/linear-v2，加载/stop/join/失败保留有效模型的事务不变。
实验schema仅扩展identity枚举；旧包仍可校验。benchmark静态checksum按模型维数
选择独立参考，不把新增维静默截断。

R4扩展研究拟合base/pawn/king/full四组；absent列权重固定0，v2统一14维契约。
selection.json及全部模型/成本证据先冻结，`r4_analysis`只在独占marker后评价test；
重算BCE/Brier、等棋局bootstrap、预定义消融对比和分层。研究JSON与部署txt分别保留。

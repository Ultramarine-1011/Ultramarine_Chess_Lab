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
`training.py` 只定义 TrainingSpec/Trainer 边界，后续加入数据清单、线性模型，
不提供假训练实现。依赖由 pyproject.toml 声明，requirements.lock 固定实际版本。

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

# 架构与接口

## 边界

```text
GUI / fastchess → UCI session → Search → Evaluator → FeatureExtractor
                                  └──── chess::Board ────┘
Python → 数据/训练、fastchess、基准、结果统计
```

chess-library 提供规则、位棋盘、合法走法、易位、EP、升变、Zobrist 与历史。
C++20 负责搜索/推理；Python 使用 python-chess 独立校验输入和结果。

| 接口 | 约定 |
|---|---|
| FeatureExtractor::extract | 白方视角，版本内维度与顺序固定 |
| Evaluator::evaluate | 当前行棋方厘兵值；终局由 Search 处理 |
| Search::run | 棋盘副本、评估器、预算和 stop token；返回合法 bestmove/PV、完整迭代结果与最终计数 |

## 搜索与 UCI

迭代加深 fail-soft Negamax/Alpha-Beta，稳定吃子/升变排序，可独立开关 QS、TT、
PV 排序。没有 LMR、空着剪枝、PVS 或并行搜索。合法走法生成后先检查将死/逼和，
再检查五十步、严格三次重复和子力不足，最后静态截断。Perft 不做和棋截断。
UCI moves 重放保留历史；FEN 无法恢复此前重复历史。

将杀基准 30000，按 ply 调整；静态值限制在将杀区间外。取消/超时只采纳最后
完整迭代；未完成一层也返回合法首着。QS 在将军时禁止 stand pat；普通局面扩展
吃子与全部升变。达到栈深度上限时中断，不能声称完成该层。

TT 校验位置、halfmove 和可逆历史摘要，分值按 ply 转换；缓存着法仅用于合法
列表内的提示。关闭 PVOrdering 不妨碍 TT 分值复用。TT 每次 run 冷启动。
普通 info 对应完整迭代，bestmove 前的 ucl_stats 包含中断迭代的最终节点/计时。
历史 R1 只有最后完整迭代计数，跨版本按固定深度比较。

主线程接收 UCI，jthread 搜索，互斥输出整行。新 position、ucinewgame、quit/EOF
停止并 join；搜索使用棋盘副本和捕获的 evaluator shared_ptr。position 先验证
FEN 与全部合法着法再替换；畸形命令报告错误并保留会话。标准 FEN 半回合 0–100、
全回合 1–32767；语法检查不是局面可达性证明。

时钟分配 remaining/movestogo + increment/2，默认 movestogo=30；扣除
MoveOverhead 后限制在可用时间内。每节点检查预算；infinite 等 stop 才发布结果。

## 特征与模型

handcrafted-v1 八维：兵/马/象/车/后数量差、兵推进、轻子中心性、双象。
手工权重 `[100,320,330,500,900,5,4,30]`。
interpretable-v2 十四维，前八维不变，后六维为孤兵、叠兵、通路兵推进、兵盾、
受攻击王环格、残局国王中心性整数分子。定义保存在 R4 协议；颜色镜像反号。
R5 在特征器内预计算通路兵掩码、合并扫描并直接分配十四维向量；保持原值与评分，
不增加 Search 中的增量状态。正式性能数据引用原始与优化版本的独立构建。

线性模型 ASCII 格式固定顺序：

```text
ucl-linear-v1  # v2 使用 ucl-linear-v2 / interpretable-v2 / weights 14
features handcrafted-v1
perspective white
temperature 400
intercept 0
weights 8 <weights>
dataset_sha256 <64 hex>
split_sha256 <64 hex>
end
```

加载时检查 4096-byte 上限、完整 SHA-256、版本、维度、有限权重及 abs<=10000。
加载器选择内置固定特征器；推理热路径直接计算 w·x，无逐点评分重复校验。
按 lround 取整、转换行棋方符号。模型/UCI 格式保持兼容。

UCI ModelSHA256 → ModelFile → Evaluator=Linear；新模型完全加载成功后停止旧
搜索并替换，失败保留有效配置。evalinfo 返回实际模型身份，eval 附加静态分数。
命令行 --features/--features-v2/--infer 和 --eval-benchmark 提供批量接口。

## Python

- records：版本/主机信息、SHA-256、原子 JSON、探索输出覆盖。
- match / benchmark：输入校验、资源清理、执行、原始结果；共用引擎配置校验。
- integrity / report：离线产物与棋谱验证、配对统计；report 内调用验证。
- dataset / r4_data、feature_data：有界下载、棋局划分/去重、C++ 特征与 Python 参考核对。
- training.fit / r4_training.fit：直接函数训练；train-only RMS、零截距 BCE、L2；
  R4 每局等权。没有额外 Trainer 协议或单实现适配器。
- r4_analysis：冻结候选后的独立测试、整局 bootstrap；r4_study 只读重建历史两批结果。
- r5_*：保留已有等价性/分析能力与研究配置；通用 runner 承担执行和身份记录，
  不再以脚本自身哈希、全仓库快照或一次性冻结文件锁定普通开发。
- r6_data：复用有界PGN/整局划分与C++特征核对；固定Stockfish冷哈希节点标注，
  同行保留棋局结果与白方教师评分；排序对每个合法子局面独立查询。
- r6_training：复用R4优化器，仅改变G/T/M软目标；validation排序选择候选，
  保留部署/重拟合核对和冻结后的单次独立test。
- r6_study：固定四组现有match配置，复用R5逐着核验（节点组可指定为D）；
  C为唯一确认性棋力判断，A/B/D探索性。没有改变引擎搜索/推理接口。

Schema 保留归档记录格式和外部输入检查；训练与部署数值格式有明确边界。
实验模式和统计约束集中于 [EXPERIMENTS.md](EXPERIMENTS.md)。

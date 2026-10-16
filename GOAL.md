# 当前工作范围：R6 Evaluation Target Alignment Study

在固定 interpretable-v2 十四维、线性模型格式和现有 C++ 搜索下，比较同一批
真实局面的棋局结果监督 G、Stockfish 教师监督 T 和混合监督 M。检验离线预测、
候选着法排序与实际棋力是否一致；不以正向 Elo 为验收条件。

按 [R6 协议](docs/r6/protocol.md) 连续完成 R6.1 数据/教师标注、R6.2 训练、
R6.3 冻结候选/独立测试、R6.4 四组实战和 R6.5 报告及提交推送。
Handcrafted 保持默认，R3–R5 已封存数据和结论不变。完成后停止，不启动 R7。

# 当前工作范围：R6 Evaluation Target Alignment Study

在固定 interpretable-v2 十四维、线性模型格式和现有 C++ 搜索下，比较同一批
真实局面的棋局结果监督 G、Stockfish 教师监督 T 和混合监督 M。检验离线预测、
候选着法排序与实际棋力是否一致；不以正向 Elo 为验收条件。

R6.1–R6.5 已完成：23998真实局面、固定教师、G/T/M训练、冻结后一次独立test、
四组1600局正式对弈及逐着核验。结果见 [R6最终报告](docs/r6/final-report.md)，
设计见 [R6协议](docs/r6/protocol.md)，复现与工程证据见
[命令入口](docs/validation/r6/commands.md)。

M08对同数据G的固定时间得分57.125%，配对95%区间[52.750%,61.625%]，
支持本条件下改善；尚未证明优于Handcrafted。默认不变，R3–R5封存证据不变。
本轮交付后停止，不启动R7或新训练/追加对局。

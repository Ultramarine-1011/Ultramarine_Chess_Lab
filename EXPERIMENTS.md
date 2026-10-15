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

## 数据与训练预留

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

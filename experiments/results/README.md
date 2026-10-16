# Selected experiment bundles

Generated runs are ignored. Keep `record.json`, `config.json`, `report.md`, raw
PGN, fastchess log and opening manifest together. Commit small selected bundles
with `git add -f experiments/results/<run>`; use release assets or external
storage for large data, with checksums and links in the record.

`smoke.json` compares the same binary under two names. It validates integration,
not playing strength. On Windows change engine paths to `build/release/ucl.exe`.


R2 最终验收入口：

- [技术报告、测试日志、环境、构建清单和 CI 快照](r2-validation-final-20261015/report.md)
- [全 8 组合、720 查询消融](r2-ablation-final-20261015/report.md)
- [R1/R2/reference、180 查询对照](r1-r2-benchmark-final-20261015/report.md)
- [R1/R2、8 开局换色共 16 局](r1-r2-match-final-20261015/report.md)

不带 `final` 的同日 R2 包是首次测量的审计记录，其中 R1 将杀分展示转换问题已在
最终包修复；旧字节保留。两批同种子对弈为流程重跑，不得合并成独立的 32 局样本。

R6入口：`r6-data-v1`保存五个有界来源PGN、划分、独立开局与数据质量；
`r6-features-v1`/`r6-labels-v1`保存共同特征与双标签；`r6-models-v1`保存
G/T/M模型、validation选择、冻结和一次test。`r6-ranking-*-v1`保留每个合法
子局面的独立教师评分；`r6-performance-v1`为同一二进制成本/搜索测量。
`r6-matches-v1/A..D`为实际正式PGN/UCI原始包，`r6-analysis-v1`为派生统计。
流程预检`r6-smoke-*`不提供棋力证据。完整方法和命令见
[R6协议](../../docs/r6/protocol.md)及[复现入口](../../docs/validation/r6/commands.md)。

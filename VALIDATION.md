# R1 验证记录（2026-10-15，Asia/Singapore）

本地引擎与实验验收基线：`fe3a23cfeeebade4e826ac8b2af2a96b34a06f50`。
双平台最终验收提交：`e603d431a721c3f883bb1843059d122ef6bd4de5`。
最终验收包含一项测试可移植性修正：使用显式 Windows/POSIX 路径覆盖空格参数，
避免把当前主机的路径分隔符写死在断言中。此后仅补充验收文档。

## 本地环境

macOS 26.7.1 / Apple Silicon，AppleClang 21.0.0.21000101，
CMake 4.4.4，Ninja 1.13.2，Python 3.14.5。
fastchess `alpha 1.8.2 20261011-ebfd64c`，完整提交见 third_party/README.md。

## 结果

| 验证 | 结果 |
|---|---|
| Release CTest | 5/5 通过 |
| Debug CTest | 5/5 通过 |
| ASan + UBSan CTest | 5/5 通过，无 sanitizer 诊断 |
| C++ 运行时检查 | 单元 27、搜索 23、Perft 14，共 64 项 |
| UCI 黑盒测试 | 6 个 unittest 通过 |
| Python 实验工具 | 5 个 unittest 通过 |
| fastchess UCI compliance | 40/40 步骤通过 |
| 干净提交 fastchess | 2 轮、4 局，候选 2 胜 0 和 2 负，无异常终局 |
| JSON Schema | 实验记录有效 |
| GitHub Actions 语法 | actionlint 1.7.12 通过 |
| 全新克隆 | 独立临时目录、全新 venv、锁定依赖安装、Release 构建和 5/5 CTest 通过 |
| GitHub 私有仓库克隆 | 从远程重新克隆到另一临时目录，全新 venv、构建和 5/5 CTest 通过 |
| Windows CI Release | MSVC 14.51，5/5 CTest 通过 |
| Windows CI Debug | MSVC 14.51，5/5 CTest 通过 |
| macOS CI Release/Debug | 两个构建分别 5/5 CTest 通过；Release fastchess 对弈通过 |
| macOS CI sanitizer | ASan/UBSan，5/5 CTest 通过 |

Perft 包括 startpos depth 4 = 197281、Kiwipete depth 3 = 97862、
残局 depth 4 = 43238、升变/易位局面 depth 3 = 9467 和 62379。
搜索分数在三种局面上与无剪枝的穷举 Minimax 对照一致。

选定结果：[`r1-smoke-20261015`](experiments/results/r1-smoke-20261015/report.md)，
同目录保存配置、完整记录、开局副本、PGN 与日志。
本次两个名称使用同一二进制，仅用于流程验证，不能推断 Elo。

双平台远程运行：[GitHub Actions #38693572181](https://github.com/Ultramarine-1011/Ultramarine_Chess_Lab/actions/runs/38693572181)，
5 个 job 全部 success。Windows 验证由 GitHub 托管 runner 执行；未在用户的
Windows 实验主机上测试硬件性能或长时间负载。

## 协作规范维护（2026-10-15）

- 范围：仅完善 AGENTS.md 的长期工作方式，并在此保留交接记录；未启动 R2。
- 版本：基于 `e6de4a06698f00989aed2472d22b9a1a2758a970` 的文档修改工作树；
  `build/release/ucl --build-info` 确认复用的 Release 产物来自该干净提交。
- 一致性检查：核对 ROADMAP.md、ARCHITECTURE.md、EXPERIMENTS.md、README.md、
  相关接口、搜索实现、测试与 CI 定义，无冲突；第一轮 NN/RL 限制改为按授权里程碑确定范围。
- 执行 `git diff --check`：通过；`ctest --preset release`：5/5 通过，
  覆盖 unit、search、perft、uci、experiments。
- 本次仅修改文档，不重跑跨平台 CI；上方 R1 CI 和目标硬件验证范围保持原有含义。
- 状态：本次维护完成，无阻塞；后续阶段等待明确授权。

# R2 进行记录（2026-10-15，Asia/Singapore）

授权范围：搜索 QS → TT → PV ordering，各自独立开关/提交；实验完整性、固定
基准、R1/R2 小样本对照及本地/CI 验证。完成 R2 后停止，不启动 R3。
起点 `628bd24`，工作树干净；重新查询 R1 CI #38693572181，5 个 job success。
本地继续使用上方 Apple Silicon 工具链和 `.venv`，fastchess 固定版本不变。

## 实验完整性修复

- 测试版本：`628bd24` + 本阶段 dirty Python/schema/test 修改；C++ 复用 R1 二进制。
- 输入配置改存 `match-config.json`，保留 fastchess 自有 `config.json`。
- validate/report 实际检查每项产物大小/SHA-256、输入配置、引擎声明与编译版本、
  PGN 引擎/换色/起始局面/终局、结果文本与头部、从 PGN 重算的全部已存统计。
  增加每轮 0/0.5/1/1.5/2 分计数。R1 历史包保留原文件和统计格式兼容。
- `.venv/bin/python -m unittest discover -s tests -p test_experiments.py`：6/6 通过；
  包含配置覆盖模拟、逐个文件篡改、统计/种子/版本篡改、缺失 PGN、路径越界、
  即使重写 PGN 哈希后仍检测结果头部/正文矛盾。
- `.venv/bin/ucl-lab validate experiments/results/r1-smoke-20261015/record.json`：通过。
- `ctest --preset release`：5/5 通过（unit/search/perft/uci/experiments）。
- 初次新增测试失败：mock subprocess.check_output 意外影响 sysctl；已缩小到
  `--version` 调用后重跑通过。这是测试夹具问题，无引擎修改。
- 下一步：QS，随后 TT 和 PV；尚未声称 R2 性能或棋力收益。

## QS 阶段

- 测试版本：`b128e0a` + dirty QS/search/UCI/test 修改；新增 Quiescence 独立开关，
  默认启用。非将军搜索吃子（含 EP）与全部升变，将军搜索全部应对，无 stand pat。
  先终局/和棋判定，再静态评估；256 ply 安全上限中止迭代，保留上一完整结果。
- 命令：`cmake --preset release -DPython3_EXECUTABLE="$PWD/.venv/bin/python"`、
  `cmake --build --preset release --parallel 4`、`build/release/ucl_tests search`、
  `ctest --preset release`：搜索 33 checks；CTest 5/5 通过。
- 命令：`cmake --preset sanitize -DPython3_EXECUTABLE="$PWD/.venv/bin/python"`、
  `cmake --build --preset sanitize --parallel 4`、`build/sanitize/ucl_tests search`：通过。
- 新测试覆盖毒兵回吃、将军时安静应对、终局优先级、严格节点限制、中途 stop
  保留完整迭代及关闭 QS 的穷举 Minimax 对照。
- 首次搜索测试崩溃：新增夹具错误地让非行棋方已处于将军；Sanitizer/Debug
  断言定位到棋盘缺王。改用合法起始局面后 Release/Sanitizer 搜索测试通过。
  顺便移除脚本编辑带来的未用变量与重复计数赋值，编译无警告。

## TT 阶段

- 测试版本：`1f5e0a0` + dirty TT/search/UCI/test 修改。
- `cmake --build --preset release --parallel 4`、`build/release/ucl_tests search`：
  91 checks 通过；`ctest --preset release`：5/5 通过。
- 覆盖将杀分数跨 ply 双向归一化、bound 保存、深度/代龄替换、强制槽冲突和完整
  主键比较、QS 开/关下与无 TT 的相同深度分数对照、97 半回合边界、重复历史与
  同 FEN 无历史区分、合法 PV 前缀、实际缓存命中和截断、独立关闭。
- TT 每次 run 新建；主键之外校验可逆历史次数指纹和半回合计数，只在剩余深度
  完全相同时复用分数。此阶段未启用 TT 着法排序，留待独立 PV ordering 提交。

## PV ordering 阶段

- 测试版本：`d17b12f` + dirty 排序/search/UCI/test 修改。
- `cmake --build --preset release --parallel 4`、`build/release/ucl_tests search`：
  659 checks；`ctest --preset release`：5/5 通过，UCI 增至 7 个 unittest。
- 固定种子 20261015 的 10 个局面，QS/TT/PV 的全部 8 种组合，固定 depth 3，
  相同 QS 语义下分数/完成深度一致，逐着验证 PV。排序关闭无提示使用；TT 关闭
  旧 PV 仍可用；默认组合确实使用 PV/TT 提示。各节点预算限制保持严格。
- UCI 黑盒同样遍历 8 种组合、Hash=1，核对分数/PV，拒绝非法布尔值/Hash。

## 基准/版本实验工具阶段

- 测试版本：`53f7477` + dirty 工具、统计输出和边界测试修改。
- 增加 benchmark-v1 Schema、冻结 10 局面、全 8 组合控制配置、重复测量中位数；
  保存最终统计/内部微秒时间、含管道往返时间和完整 UCI transcript，支持完整性验证。
- 历史构建：`.venv/bin/python scripts/build_revision.py e603d431a721c3f883bb1843059d122ef6bd4de5`
  通过，独立 clean worktree 构建，manifest/build.log 保留于 `.tools/engines/<SHA>/`。
- 增加 revision/ablation 身份保护（不同版本/二进制、相同编译控制，或同二进制不同
  开关）、manifest 配置生成工具和 Windows 长实验准备程序。未运行 Windows 主机实验。
- 诊断 `.tools/r2-diagnostic` 被过期二进制版本检查拦截（预期保护生效）。重新
  configure/build 后 `.tools/r2-diagnostic-2`（dirty，仅诊断）160 查询成功并通过 validate。
  正式测量将在干净提交重做，诊断数值不作为交付结论。
- `cmake --build --preset release --parallel 4`、`build/release/ucl_tests search`：
  新增 EP/安静升变 horizon、mate-in-two 距离、TT/PV stop/再次搜索历史隔离覆盖；
  `ctest --preset release`：5/5 通过（UCI 8、Python 实验 7 unittest）。
- `cmake --preset debug -DPython3_EXECUTABLE="$PWD/.venv/bin/python"`、
  `cmake --build --preset debug --parallel 4`、`ctest --preset debug`：5/5 通过。
- `cmake --preset sanitize -DPython3_EXECUTABLE="$PWD/.venv/bin/python"`、
  `cmake --build --preset sanitize --parallel 4`、`ctest --preset sanitize`：5/5 通过，
  无 ASan/UBSan 诊断。扩展搜索矩阵的 CTest timeout 调为 180s，避免慢速 Debug 主机误报。
- 尚待：干净版本最终全套验证、正式消融/版本基准与轻量赛、推送及双平台 CI。

## 正式基准审计：将杀分数展示修正

- 干净 `046d5b043ec5072238e8708c9f0df8e9d57834ee`：Mac Release/Debug/Sanitizer
  各 5/5 通过（搜索 685 checks）。日志暂存 `r2-validation-20261015`。
- 此版本首次正式实验：`r2-ablation-20261015` 720 查询、
  `r1-r2-benchmark-20261015` 180 查询和 `r1-r2-match-20261015` 16 局均完成并
  通过文件/统计完整性校验。UCI compliance 40/40。
- 进一步逐查询比较 R1 与 R2-reference 时，发现 Python 通用
  `score(mate_score=30000)` 按 mate 的步数而非 UCL 的 ply 距离转换；输棋 mate -2
  被展示为 -29998，UCL 原始为 -29996。节点、完成深度、着法和 PV 无差异。
  这是基准归一化错误，不是搜索差异。修正正 mate N→2N−1、负 mate −N→2N ply，
  增加正负 mate/零/普通分值回归测试，随后重新生成正式对照包。
- 上述首次包保留为审计证据，后续修正版作为最终基准；不静默覆盖或删除记录。
  fastchess 原始日志自动打印的 Elo/LOS 不是 UCL 的结论，16 局只用于轻量验收。

## R2 最终验收（2026-10-15，Asia/Singapore）

**状态：本轮授权 R2 条件满足，停止；未开始 R3。**
最终代码/实验版本 `eee9d44b5a73b36f06ae837e079a6afc66f8caaf`，下述正式运行起点
工作树干净。验收后仅追加本节、路线图及已审核的小型实验包，无算法改动。
R1 验收提交保持 `e603d431a721c3f883bb1843059d122ef6bd4de5`。

完整 [技术报告](experiments/results/r2-validation-final-20261015/report.md)、
[环境](experiments/results/r2-validation-final-20261015/environment.json)、
[R1 构建清单](experiments/results/r2-validation-final-20261015/r1-build-manifest.json)、
[R2 构建清单](experiments/results/r2-validation-final-20261015/r2-build-manifest.json)
保留版本、SHA-256、编译器/参数、硬件和精确构建命令。
本机为 Apple A18 Pro / 6 逻辑 CPU / 8 GiB，macOS 26.7.1；版本等同上方工具链。

### 精确命令及结果

```sh
cmake --preset release -DPython3_EXECUTABLE="$PWD/.venv/bin/python"
cmake --build --preset release --parallel 4
ctest --preset release
build/release/ucl_tests search
build/release/ucl --build-info
cmake --preset debug -DPython3_EXECUTABLE="$PWD/.venv/bin/python"
cmake --build --preset debug --parallel 4
ctest --preset debug
cmake --preset sanitize -DPython3_EXECUTABLE="$PWD/.venv/bin/python"
cmake --build --preset sanitize --parallel 4
ctest --preset sanitize
.venv/bin/python scripts/build_revision.py HEAD
.venv/bin/python scripts/prepare_comparison.py \
  --baseline .tools/engines/e603d431a721c3f883bb1843059d122ef6bd4de5/manifest.json \
  --candidate .tools/engines/eee9d44b5a73b36f06ae837e079a6afc66f8caaf/manifest.json \
  --output .tools/r2-comparison-final-20261015
.venv/bin/ucl-lab benchmark --config experiments/configs/r2-ablation.json \
  --output experiments/results/r2-ablation-final-20261015
.venv/bin/ucl-lab validate experiments/results/r2-ablation-final-20261015/record.json
.venv/bin/ucl-lab benchmark --config .tools/r2-comparison-final-20261015/benchmark.json \
  --output experiments/results/r1-r2-benchmark-final-20261015
.venv/bin/ucl-lab validate experiments/results/r1-r2-benchmark-final-20261015/record.json
.tools/bin/fastchess --compliance .tools/engines/eee9d44b5a73b36f06ae837e079a6afc66f8caaf/ucl
.venv/bin/ucl-lab match --config .tools/r2-comparison-final-20261015/match.json \
  --output experiments/results/r1-r2-match-final-20261015 --fastchess .tools/bin/fastchess
.venv/bin/ucl-lab validate experiments/results/r1-r2-match-final-20261015/record.json
.venv/bin/python experiments/results/r2-validation-final-20261015/check_reference.py
```

| 验证 | 实际结果 / 证据 |
|---|---|
| Mac Release | 5/5 CTest，[log](experiments/results/r2-validation-final-20261015/release.log) |
| Mac Debug | 5/5 CTest，[log](experiments/results/r2-validation-final-20261015/debug.log) |
| Mac ASan/UBSan | 5/5 CTest，无诊断，[log](experiments/results/r2-validation-final-20261015/sanitize.log) |
| C++ / Perft | unit 27、search 685、perft 14 checks；原 R1 Perft 数值未变 |
| UCI / Python 实验 | 各 8 unittest；含全部开关、实际基准留档/篡改、版本身份与 mate 转换 |
| fastchess compliance | 40/40，[log](experiments/results/r2-validation-final-20261015/experiment-commands.log) |
| 算法消融 | 8 组合 × 10 局面 × 3 重复 × 3 限制 = 720 查询，[包](experiments/results/r2-ablation-final-20261015/report.md) |
| 版本基准 | 3 引擎配置 × 10 局面 × 3 重复 × 2 深度 = 180 查询，[包](experiments/results/r1-r2-benchmark-final-20261015/report.md) |
| R1 语义回归 | R1 vs R2-reference 的 60 查询，score/depth/nodes/move/PV 零差异，[结果](experiments/results/r2-validation-final-20261015/reference-comparison.json) |
| 版本小样本赛 | 两个不同完整 SHA/二进制，8 开局/16 局，13 W / 3 D / 0 L，无异常终局，[包](experiments/results/r1-r2-match-final-20261015/report.md) |
| 全部包完整性 | 文件大小/哈希、PGN/配对/终局与统计重算通过，R1 历史包也通过 |

### 量化结论及限制

- depth 4 同 QS 语义：QS-only 389,687 nodes / 111.08ms，默认 QS+TT+PV 为
  266,968 / 93.59ms；节点少 31.49%，这批短时测量 wall 少 15.75%。各局面重复
  中位数求和，完整原始计时/NPS/TT 指标在包内；不将三次重复当成性能显著性检验。
- 跨版本批次：depth 4 R1 91,000 / 13.31ms，默认 R2 266,968 / 80.02ms。
  QS 扩展战术边界，工作量更大；不声称默认 R2 比 R1 更快。TT 分配和路径检查也
  有成本，尤其浅层。关闭新优化的 R2 保持 R1 搜索语义。
- 六项窄范围战术标签：depth 1 R1 5/6 → R2 6/6，修正毒兵；depth 4 均 6/6。
- 对弈得分 90.625%，配对五档计数 [0,0,0,3,5]，按轮 bootstrap CI95
  [81.25%,96.875%]。15 局正常、1 局步数裁决；小样本、少开局、同深度不同计算量，
  不推导 Elo。两批同种子流程重跑不得合并为 32 局独立样本。
- TT 为 64 位主键/历史指纹，保留通常概率碰撞风险；每次 run 清空，PV 可在缓存处
  结束为合法前缀；256 ply 安全上限中止未完成迭代。FEN 无法恢复此前重复历史。
- 用户 Windows 实验主机未执行持续实验；正式大样本棋力、SPRT/显著性检验未运行。
  相应硬件/电源/线程、开局、预注册和运行步骤已写入 EXPERIMENTS.md。

### 推送与跨平台 CI

代码已推送 origin/main。`046d5b0` 的首次 CI #38699985781 五个 job 全 success；
修正 mate 转换后的最终代码 `eee9d44` 对应
[GitHub Actions #38700282364](https://github.com/Ultramarine-1011/Ultramarine_Chess_Lab/actions/runs/38700282364)，
macOS Release/Debug、Windows Release/Debug、macOS sanitizer 五个 job 全 success，
Mac Release fastchess smoke 通过。
[CI 原始状态快照](experiments/results/r2-validation-final-20261015/ci.json) 留档。
Windows 证据来自托管 runner，不代表用户实验主机验收。本轮无需 CI 修复。

归档检查：`git diff --cached --check` 仅报告两批原始 fastchess.log / games.pgn
各自文件末尾的空行（4 条）；为保留原始哈希未改写产物。执行
`git -c core.whitespace=-blank-at-eof diff --cached --check` 通过。
最终验收文档修改后 `ctest --preset release` 再次 5/5 通过。

## Skills 配置优化（2026-10-15，已完成）

授权范围：精简并验证 Skills，允许提交/推送；不启动 R3。
起点 `8a7d450` 干净且与 origin/main 一致，最新已有代码 CI 五项 success。
已创建仓库级 `ucl-engine-validation`、`ucl-experiment-audit`，固定版本安装
`gh-fix-ci`；跳过目前无 Notebook 用途的 `jupyter-notebook`。复用现有工具，
不改引擎、统计实现和项目 Python 依赖。
配置决策、运行时兼容问题与可复现探针见
[审计记录](docs/validation/skills-20261015/report.md)。
桌面运行时已从根目录/tests 成功发现三个唯一启用的仓库 Skill，未修改全局配置。
三个 Skill 的 quick_validate、引用/UI 元数据检查通过。手动按新 Skill 实际执行：
历史三个正式包 validate/report 通过，实验 Python 8/8，Release CTest 5/5；
gh helper 的历史失败 Actions 日志读取 status=ok，无 PR 返回 1 为预期。
首次回归误将 venv 符号链接解析成系统 Python，缺包导致 3/5；按 README 修正解释器
重试成功，失败/成功命令与日志均保留。测试版本为 `8a7d450` + dirty Skills/docs。
配置提交 `9606cdb30db76efe7253d8b621fea25344f079b5` 已推送 origin/main。
该干净版本重新 configure/build、Release CTest 5/5；临时独立 Git 克隆的
root/tests Skills 发现及所有内容哈希一致，见审计记录的 clean-clone/clean-release
证据。对应
[Actions #38705038767](https://github.com/Ultramarine-1011/Ultramarine_Chess_Lab/actions/runs/38705038767)
macOS/Windows Release/Debug、macOS sanitizer 五项 success，Mac fastchess smoke
通过；[CI 快照](docs/validation/skills-20261015/ci.json)。
Windows Codex 桌面调用、用户 Windows 实验主机未实测；未独立测试模型隐式选择。
保留全局 Skills，仓库只有三个目标 Skill，不添加无关能力；本轮完成，未启动 R3。
最后仅追加本节及文档证据，以 `[skip ci]` 文档收尾提交同步；其前的最终 Release
与上述配置提交 CI 证据保持有效。

## R3.1 — 数据与协议（2026-10-15）

授权完整 R3.1–R3.5，起点 `b9fac65cbcb68b492090b076f333dff861580a86`，
干净 main=origin/main；最新已有代码 Actions #38705038767 五项 success。
已读 ROADMAP/架构/历史协议、相关源码测试和 R2/Skills 验证证据。

- 恢复 `b128e0a` 的历史 EXPERIMENTS.md 内容，保留 R2 固定实验/Windows
  规范，并移除误复制的架构；R3 参数在训练前冻结于 docs/r3/protocol.md。
- 修复 PGN 的自然终局必须匹配棋盘结果；外部 adjudication 单独保留，
  不能与强制终局矛盾。Lichess Normal（含认输）按来源语义检查。
- Lichess CC0 January 2017，HTTP 206，精确 2,097,152 byte 前缀（全文件
  1,902,198,021 bytes，未完整下载），前 3000 完整局。保留来源/许可/HTTP
  headers/获取时间/源及产物 SHA-256。原压缩前缀留于本机 .tools；可按 Range
  重取；Git 保留选定 PGN gzip 784,539 bytes、局面 gzip 430,905 bytes、划分。
- 固定规则保留 908 局；train/validation/test 634/150/124 局，
  3972/922/794 局面，总 5688。跨集合（含颜色镜像）移除 4 个局面出现，
  集合内重复移除 1。完整计数/游戏身份/哈希见 experiments/results/r3-data-v1。
- `.venv/bin/python -m ucl.dataset --output .tools/r3-dataset-v1` 成功；
  `validate_dataset("experiments/results/r3-data-v1")` 从真实源棋谱重建完全一致。
  源数据是方便的时间顺序小样本；结果标签有噪声，不是精确 minimax value。
- 测试版本：上述 SHA + dirty R3.1。按 README configure/build Release，
  `ctest --preset release -R '^(experiments|research)$'` 2/2，
  `ctest --preset release` 6/6，日志见 docs/validation/r3/r31-*.log。
  R2 正式 match 的原始 bundle validate 通过。
- 初次两个 fixture 断言错误（起始局面颜色镜像相同、fixture 含和棋），已修正；
  初次通配发现误将独立 UCI runner 纳入 unittest，保留 r31-discovery-failed.log，
  改为独立 research CTest，未改变已有 UCI runner。
  一次历史路径 r1-smoke-clean 不存在的审计命令失败，不声称其通过。
- CI 使用三局真实 CC0 fixture，无网络训练依赖；本阶段不涉及 C++ 核心修改，
  未另跑 Debug/sanitizer。后续 R3.2–R3.5 尚待实施。
R3.1 代码/数据提交 `fcc652370c646ed6bfd37d0c308da4ab4c44a3ba` 已推送。
[对应 Actions](https://github.com/Ultramarine-1011/Ultramarine_Chess_Lab/actions/runs/38708443580)
已启动，状态待检查；本记录另作可恢复的文档提交。

## R3.2 — C++ 特征导出与一致性（2026-10-15）

R3.1 对应 Actions #38708443580 五项全部 success；快照 r31-ci.json。
本阶段测试基底 `5065f0962e5023576080961c76574697af35e7b0` + dirty R3.2。
`ucl --features` 复用原 position parser/HandcraftedFeatures，非法 FEN 明确失败。
Python 逐行检查版本、八维有限值、独立特征实现和原权重评分，训练输入来自 C++。

- 5688 个正式数据局面诊断导出全部精确一致；局面 ID/棋局 ID/标签/划分均保留。
- 随机合法走棋及颜色镜像、原十局面特殊走法/残局、正负符号和原评分取整边界，
  以及非法维度/NaN/Inf/bool/版本/FEN 测试通过；handcrafted-v1 语义未变。
- 精确命令见 docs/validation/r3/commands.md，Release targeted 3/3，
  Release/Debug/ASan+UBSan 各 6/6。日志 r32-*.log。没有 sanitizer 诊断。
- 初次测试错误地调用 python-chess legal_moves 属性，已修正并保留失败日志。
  更新取整测试时两个本地 preset 验证序列短暂重叠，均已退出成功；未用于性能测量。
- 正式 clean binary 特征导出在本阶段代码提交后执行，随后以原始哈希归档。
  R3.3 未训练，冻结测试集未用于模型选择。
正式特征导出：clean `e5b625fe70088935c6f3d41bf3e77f8ea574ccb1` Release，
5688/5688 精确一致；features gzip SHA-256
`ba76d6eab0bc6fffbd25c385a357589fa9646532e2dc47ef32219fedbe69a9f6`。
归档于 experiments/results/r3-features-v1（含源清单/划分/binary 哈希与 build info）。
R3.2 [Actions #38709009820](https://github.com/Ultramarine-1011/Ultramarine_Chess_Lab/actions/runs/38709009820)
运行中，后续必须核对最终状态。

R3.2 代码 Actions #38709009820 五项全部 success（r32-ci.json）。
训练前审查发现 v1 每 8 ply 采样只包含白走局面，属于分布缺陷。尚未拟合任何
模型或查看测试指标；按预注册修正规则改为从 ply16 开始间隔 7 ply，保留 v1
原始包与旧采样版本的重建能力，重新冻结 v2。来源、过滤、game ID 和游戏划分
保持不变。两种走棋方的回归检查已加入；正式训练仅使用 v2。
修正版的完整计数/哈希见 experiments/results/r3-data-v2；
`ctest --preset release -R '^research$'`、完整 Release 6/6 通过，
命令/日志 r31-v2-*.log；测试基底 61282b6 + dirty sampling 修复。

## R3.3 — 训练实现（2026-10-15，正式训练前）

v2 数据 908 局/6039 局面：train/validation/test 4208/990/841；游戏划分
634/150/124 不变。6039 个 C++/Python 特征与手工分数精确一致；
clean exporter `e5b625fe70088935c6f3d41bf3e77f8ea574ccb1`，
features SHA-256 `6a061c95073f71ff25909d4eaaa7407a14e926c5612c453c0850cca230e633b4`。

实现 NumPy/SciPy float64 fractional BCE、解析梯度、train-only RMS、零截距、
手工 beta 中心 L2，候选 lambda 与停止条件遵守预注册协议。保留所有候选与
收敛信息；选择/模型冻结先于独占 marker 的正式 test 步骤。模型严格 ASCII
部署 Schema 和严格 JSON manifest，哈希/维度/有限值/版本验证均覆盖。
Python/数值依赖锁定 numpy=2.5.4、scipy=1.18.1，官方 API 依据：
https://docs.scipy.org/doc/scipy/reference/optimize.minimize-lbfgsb.html
和 https://numpy.org/doc/stable/reference/generated/numpy.logaddexp.html 。

测试基底 `1f512d491b0d8fa960e27b1d5e060aa5649235a1` + dirty R3.3，
`ctest --preset release -R '^research$'` 通过（8 unittest，含梯度有限差分、
极端 logit、确定性、schema/hash 篡改，以及 fit 绝不调用 test 的集成 guard），
完整 `ctest --preset release` 6/6。日志 r33-targeted/release.log。
本阶段为 Python 训练实现，未改变 C++ 搜索，未额外重跑 Debug/sanitizer。
正式模型将在此代码提交后从干净版本拟合；未执行 test 指标或根据 test 调参。

R3.3 正式训练完成：clean `09335c08291f3a7f3c831372fda750903cef4ad5`。
确切命令为 README 的 fit/test 两步，均指定
`OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 OMP_NUM_THREADS=1`，
输出 `experiments/results/r3-model-v1`。6 候选全部收敛，validation 选 λ=.0001。
正式 test 仅一次：841 局面/124 局，手工 BCE .587908078 / Brier .189141550，
正则模型 .583818366 / .188307783。以棋局聚类的差值区间均跨零，不能断言总体
改善；早期与和棋标签分层退步。详细参数/成本/指标/限制见 docs/r3/model-report.md。
部署 SHA-256 `446d18379cfa66e018c4be56218db044339e4be137309c9a17dfbab69874269b`。
同配置第二次仅 train/validation 拟合至 `.tools/r3-reproduce-v1`，模型字节一致。
原始 test 中 later_ply48_160 为标签文字错误，实际 predicate >40（v2 首个44），
已在报告明确说明；不重跑/改写正式 test。其余原始记录和冻结 marker 均保留。
R3.1 v2 Actions #38709478484 五项 success；R3.3 Actions #38709750930
Mac 三项 success，Windows Release/Debug 失败，正在按 gh-fix-ci 调查修复；
CI 快照 r31-v2-ci.json / r33-ci.json。R3.4 和 R3.5 待完成。

### R3.3 CI 修复

`gh run view 38709750930 --log-failed` 定位 Windows 两个 job 的 research
训练输入 SHA mismatch，其他测试全通过；日志 r33-windows-failed.log.gz。
Windows Git 默认文本 CRLF 转换改变清单/划分字节，而 gzip 不变。
新增 `.gitattributes` 固定文本 LF、压缩文件 binary，保留冻结文件原始字节/hash。
顺带修正未来分层输出标签为 later_ply41_160；不修改/重算已有冻结 test。
此前一条文档提交将尚未核查的 R3.3 CI 误写为全通过，已更正并保留失败证据。
这是记录错误，不是一次成功 CI；以之后精确 SHA 对应的 run 为最终依据。

修复前一次 core.autocrlf=true 临时克隆复现相同 hash mismatch。
原始 Actions 日志含行尾空白，首个 diff --check 阻止提交；改为 gzip 原样保留。

R3.3 修复验证：clean checkout with `git -c core.autocrlf=true clone --no-local`
到 `.tools/r3-windows-lineendings-fixed`，6039 行训练输入哈希和冻结模型哈希全部
匹配。修复提交 `6113aef665c60e7d98caae793ad845711a8af082` 的
[Actions #38710461241](https://github.com/Ultramarine-1011/Ultramarine_Chess_Lab/actions/runs/38710461241)
五项全部 success；快照 r33-fixed-ci.json。R3.3 工程/模型验收完成，未改模型权重。

## R3.4 — LinearEvaluator 与 UCI 部署（2026-10-15）

测试基底 `6113aef665c60e7d98caae793ad845711a8af082` + dirty R3.4。
轻量 C++ LinearEvaluator 复用原 8 维 extractor，按严格 ASCII Schema/有限值/
范围/特征版本/完整 SHA-256 加载；固定 MIT PicoSHA2 原头与许可，来源及哈希
见 third_party/README.md。Handcrafted 默认、固定权重与搜索源文件均未改变。

UCI 支持 ModelSHA256 → ModelFile → Evaluator 顺序、实际 evalinfo、独立切回。
模型完整验证后 stop/join 才替换，搜索按值捕获 shared_ptr<const Evaluator>；
失败明确报错并保留原有效配置。路径空格、运行中 reload/switch、hash 失败、
无模型切换拒绝与终局处理均覆盖。Python match/benchmark 实际 UCI probe 核对
身份，统一选项顺序/路径，保存模型副本；Schema 仅增可选 evaluation 字段，
旧包保持兼容。完整性校验拒绝 model/evaluator 身份篡改。

- 6039 个正式局面 Python/C++ double 推理差值 <1e-9 cp，取整/符号全相同；
  原手工权重、half-cp 正负边界、畸形/额外字段/版本/维度/NaN/Inf/超范围/
  文件大小/hash 错误均验证。
- configure/build 命令同 commands.md，targeted unit/research/uci/experiments
  4/4，Release/Debug/ASan+UBSan 各 6/6，无 sanitizer 诊断；日志 r34-*.log。
  当前 UCI 10 unittest，research 10 unittest；原 search/perft 无回归。
- `.tools/bin/fastchess --compliance "$PWD/build/release/ucl"` 40/40，原始
  日志 gzip 保留。`--eval-benchmark` 7 次交替顺序的静态调用 CLI 诊断通过；
  诊断不作为性能结论，正式计时待 clean binary。
- 初次 UCI fixture 的白走局面正将军对方国王，原 parser 正确拒绝，修正为合法
  queen-d2；一次脚本编辑误插入另一个测试方法，修正后全回归。失败日志保留。
- 已准备固定 16 个自编标准开局与协议一致的 32 局配置；正式对弈尚未执行。

## R3.5 — 冻结实验配置（2026-10-15，运行前）

已准备16个不同开局的合法 SAN 重放清单/EPD，未参考实验结果筛选。与预注册
协议一致，32局/16换色轮，5+0.05、无深度限制、maxmoves150、并发1、Hash16、
QS/TT/PV=true、MoveOverhead10、seed20261015、timeout1200s，同一 R3 binary。
十局面固定深度3/4、三次重复；静态调用7轮交替顺序、每模型/局面100000次。
静态证据最小扩展既有 benchmark 的 tools/artifacts 与可选配置，validate
重算 checksum/覆盖/中位数，report 分开显示；不另造比赛或统计系统。

基底 `96e41da2b1174252c93f309a02f3efe526860703` + dirty R3.5 Python/config/docs：
`ctest --preset release -R '^(uci|experiments)$'` 2/2、完整 Release 6/6；
日志 r35-targeted/release.log。新模型 benchmark 集成测试也验证保留身份与篡改。
正式实验必须在本配置提交及 clean rebuild 后运行；未执行正式 match。

R3.5 正式实验运行状态（可恢复记录）：clean code/binary
`476ceeee4b96d0ee1f2ffcf1f572f08833c4bf70`，binary SHA-256
`95bb42aaac9d770446f854e80d9562fc2bde89f88db2766aec0fb6a63986729e`。
按 README 运行 benchmark 至 `experiments/results/r3-benchmark-final-20261015`，
120查询和70条静态计时全部完成；validate/report 通过。depth4 hand/linear
266968/287201 nodes、76.152790/81.244622ms；静态 23.016249/24.300165ns/call。
同深度变更 evaluator 会改变搜索树，不能把节点差异当纯推理开销或 Elo。
32局正式赛于 2026-10-15 09:19:52 UTC 开始，输出
`experiments/results/r3-match-final-20261015`；record.json 在运行中保留命令/
身份/硬件，fastchess.log 和 games.pgn 持续写入。仍为本次唯一正式赛，
不要因会话恢复而重复启动、换种子或调整权重。未达到最终验收，不启动 R4。
R3.4 Actions #38711662455 五项全部 success；最新配置 Actions #38711949849
另行核查。运行中不启动本地 builds/tests 干扰计时。

R3.5 配置版本 Actions #38711949849 五项全部 success（r35-ci.json）；
R3.4 快照 r34-ci.json。额外来源审查：月库名为 January 2017，但首3000局原始
UTCDate/UTCTime 实际窗口为 2016-12-31 23:00:00–23:16:53 UTC；不推测其原因。
这是非常窄的方便样本，不具有全月/全平台代表性；冻结后不据此换数据或重训。
原始源码比对：从 R3 起点 b9fac65 到476ceee，engine/src/search.cpp 与
engine/src/evaluator.cpp 无任何差异，保留 R1/R2 算法与原手工特征/权重。

## R3 最终研究验收（2026-10-15）

R3.1–R3.5 全部完成，未启动 R4。正式报告：docs/r3/final-report.md。
真实数据、冻结独立测试、C++ 推理、UCI 部署、benchmark 和 fastchess 闭环已完成；
工程与研究验收通过，**没有证据证明棋力提升**，继续使用 Handcrafted 默认。

### 最终量化与完整性

- 正式代码完整 SHA `476ceeee4b96d0ee1f2ffcf1f572f08833c4bf70`，clean binary
  SHA-256 `95bb42aaac9d770446f854e80d9562fc2bde89f88db2766aec0fb6a63986729e`；
  同一 binary/evaluator 选项对照，冻结模型 hash `446d18379cfa66e018c4be56218db044339e4be137309c9a17dfbab69874269b`。
  精确 binary/configure/build 日志保留于 .tools/r3-frozen-engine-476ceee，不入 Git。
- Mac 正式32局/16轮（2026-10-15 09:19:52–09:27:04 UTC）：12W/5D/15L，
  得分45.3125%，五档计数[4,1,7,2,2]，配对bootstrap CI95 [28.125%,60.9375%]。
  32局自然结束，0裁决/异常；27将杀、1重复、1子力不足、3五十步；16指定开局
  各恰好2局。仅本批正式赛，未追加/调参/换种子。fastchess自动Elo不作研究结论。
- depth4 hand/linear：266968/287201 nodes，76.152790/81.244622ms；静态
  23.016249/24.300165ns/call。独立解释推理、树变化、耗时与实际对弈。
- 离线 test：BCE .587908078→.583818366，Brier .189141550→.188307783，
  棋局聚类差值区间均跨零，早期/和棋标签分层退步，不能断言泛化改善。
- 正式包完整哈希/元信息/模型/合法PGN/配对/终局/统计重算 validate/report 通过。
  最终审计覆盖两个数据版本、6039特征输入、冻结模型、16开局、9个保留历史及
  正式 bundle；命令 `.venv/bin/python docs/validation/r3/audit_final.py`，
  r35-final-audit.json/log 保存结果。此审计不重跑比赛、不重新评价 test 指标。
- 最终归档前 configure/build/Release CTest 6/6，pip check 无依赖冲突；
  测试版本476ceee + dirty docs/archive/setup metadata，精确日志
  r35-acceptance-configure/build/release.log 与 r35-dependencies.log。
  数值库 metadata 显示 Requires-Python>=3.12，故同步 pyproject/CMake/README/
  requirements 的最低版本；不影响此前3.14训练或正式C++ binary，不重跑正式实验。
- macOS/Windows Release/Debug、macOS sanitizer 的正式代码 Actions #38711949849
  五项success，R3.4 #38711662455亦五项success；快照 r35-ci/r34-ci.json。
  归档提交还将触发一次当前主分支CI，最终状态在后续同步记录。

### 边界和后续

保留历史源/失败记录，无搜索或手工评估算法改动，无新增特征/神经网络/MCTS。
来源窗口仅约17分钟，数据/开局范围小；玩家相关性、标签噪声和bootstrap限制
不能被工程通过抵消。Windows持续实验主机、长赛/SPRT和广泛外推未验证。
R4 需另行授权，建议先扩大跨日期数据与独立开局，再评估特征/模型扩展。

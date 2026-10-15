# Ultramarine Chess Lab (UCL)

可运行、可比较、可复现的 UCI 国际象棋引擎研究项目。C++20 负责引擎与推理，
Python 负责数据、训练接口、实验和统计。R1 经典基线保留可构建；R2 提供 QS、TT 和 PV 排序，R3 增加可选监督线性评估，默认仍用手工评估。

## 从全新克隆开始：macOS

前置条件：Git、Apple Command Line Tools、Python 3.12+、CMake 3.24+、Ninja。
首次安装工具：`xcode-select --install`，然后 `brew install cmake ninja python gh`。

```sh
git clone https://github.com/Ultramarine-1011/Ultramarine_Chess_Lab.git Ultramarine_Chess_Lab
cd Ultramarine_Chess_Lab
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.lock
python -m pip install --no-deps -e .
cmake --preset release -DPython3_EXECUTABLE="$PWD/.venv/bin/python"
cmake --build --preset release --parallel 4
ctest --preset release
./build/release/ucl
```

引擎内依赖已随仓库固定保存，CMake 不下载依赖；Python 首次安装需要网络。
只构建引擎时可用 `cmake -S . -B build/engine -G Ninja -DBUILD_TESTING=OFF -DCMAKE_BUILD_TYPE=Release`，
再运行 `cmake --build build/engine`，无需 Python 包或 fastchess。

## Windows

安装 Git、Python 3.12+、CMake 3.24+、Ninja 和 Visual Studio 2022/2026 C++
桌面开发工具。在 **Developer PowerShell for VS** 中执行：

```powershell
git clone https://github.com/Ultramarine-1011/Ultramarine_Chess_Lab.git Ultramarine_Chess_Lab
cd Ultramarine_Chess_Lab
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock
.\.venv\Scripts\python.exe -m pip install --no-deps -e .
cmake --preset release "-DPython3_EXECUTABLE=$PWD/.venv/Scripts/python.exe"
cmake --build --preset release --parallel 4
ctest --preset release
.\build\release\ucl.exe
```

无需激活虚拟环境或修改执行策略。Debug 使用 `debug` preset；macOS 的
ASan/UBSan 使用 `sanitize`。CI 在 macOS/Windows 分别构建 Release 和 Debug。

## UCI 使用

启动引擎后逐行输入；收到 `bestmove` 后再输入下一条 `position`：

```text
uci
isready
position startpos moves e2e4 e7e5
go depth 4
quit
```

支持 `position fen ... moves ...`、`ucinewgame`、`go depth/nodes/movetime`、
`wtime/btime/winc/binc/movestogo`、`go infinite`、`stop`、`isready`、`quit`。
选项 `MoveOverhead`（默认 10ms）、`Quiescence` / `UseTT` / `PVOrdering`（默认 true）、
`Hash`（默认 16 MiB，1–1024）；深度上限 128；无参数 `go` 默认深度 5。
无合法走法输出 `bestmove 0000`。搜索期间仍可响应 `isready` 和 `stop`。
首版仅标准国际象棋，不支持 Chess960、ponder、searchmoves、Threads。

`./build/release/ucl --build-info` 输出编译器、参数、配置和代码版本 JSON。
每次提交后重新 configure/build，才能让编译版本与实验代码一致。

## 自动对弈

macOS 在激活的虚拟环境中：

```sh
python scripts/bootstrap_fastchess.py
ucl-lab match --config experiments/configs/smoke.json \
  --output experiments/results/smoke-001 --fastchess .tools/bin/fastchess
ucl-lab validate experiments/results/smoke-001/record.json
ucl-lab report experiments/results/smoke-001/record.json
```

运行前提交全部修改，重新 configure/build。同名输出目录不可覆盖。
`smoke.json` 使用同一个引擎、微型固定开局集进行 2 轮换色共 4 局，只验证流程。
Windows 可在 MSYS2 UCRT64 中编译 fastchess，或使用官方 Windows 可执行文件；
将配置的引擎路径改为 `build/release/ucl.exe`，再用
`.\.venv\Scripts\ucl-lab.exe ... --fastchess <fastchess.exe路径>`。

## 搜索基准与跨版本对比

先提交代码并重新 configure/build，再执行三次重复、全 8 种开关组合的基准：

```sh
ucl-lab benchmark --config experiments/configs/r2-ablation.json \
  --output experiments/results/r2-ablation-001
ucl-lab validate experiments/results/r2-ablation-001/record.json
```

从指定提交独立构建保留的 R1 和候选版本（输出路径以完整 SHA 命名）：

```sh
python scripts/build_revision.py e603d431a721c3f883bb1843059d122ef6bd4de5
python scripts/build_revision.py HEAD
python scripts/prepare_comparison.py \
  --baseline .tools/engines/e603d431a721c3f883bb1843059d122ef6bd4de5/manifest.json \
  --candidate .tools/engines/<候选完整SHA>/manifest.json --output .tools/comparison-001
ucl-lab benchmark --config .tools/comparison-001/benchmark.json \
  --output experiments/results/version-bench-001
ucl-lab match --config .tools/comparison-001/match.json \
  --output experiments/results/version-match-001 --fastchess .tools/bin/fastchess
```

输出目录禁止覆盖；已存在的版本构建直接复用 manifest。Windows 使用对应 `.venv`
Python/CLI 路径，在 VS Developer PowerShell 运行相同步骤。实际原始证据和限制见
[验证记录](VALIDATION.md)；长实验条件见 [实验规范](EXPERIMENTS.md)。

## Codex Skills

仓库只维护三项 `.agents/skills/` 能力，随 `git clone` / `git pull` 同步到
macOS 和 Windows。无需复制到用户 Skills 目录、创建符号链接或设置绝对路径。
Codex 从仓库根目录或子目录发现 Skills；更新后可在下一轮通过技能选择器查看，
若未刷新则重启 Codex。发现机制见 [官方说明](https://learn.chatgpt.com/docs/build-skills)。

| Skill | 用途 / 调用示例 |
| --- | --- |
| `ucl-engine-validation` | `$ucl-engine-validation 验证当前授权改动并记录证据` |
| `ucl-experiment-audit` | `$ucl-experiment-audit 审计 experiments/results/<bundle>/record.json 及统计结论` |
| `gh-fix-ci` | `$gh-fix-ci 检查指定 PR 或提交的 Actions 失败，并在授权范围内修复` |

保留自动匹配；前两项分别负责工程正确性和实验结论，复用现有测试与 CLI。
`gh-fix-ci` 需要 Python 3.11+、Git、GitHub CLI 和本机 `gh auth login`；
Windows 同样需要安装 GitHub CLI 并在本机登录。
无 PR 的分支推送按提交 SHA 使用 `gh run list/view`，不强行创建 PR。
其他两项依赖上述现有工程环境，审计历史包无需原机器上的引擎二进制。

运行时发现验证（仅需标准库和可用的 Codex CLI；从仓库根目录运行）：

```text
python docs/validation/skills-20261015/probe_discovery.py <codex可执行文件路径>
```

不重复安装内置 `skill-creator` / `skill-installer` / `openai-docs`。
当前 R3 使用脚本流程，没有 Notebook 需求，暂不安装 `jupyter-notebook`；
将来需要 `.ipynb` 时再评估。全局文档、表格、浏览器和插件 Skills 不复制进本项目，也不为本项目
卸载其他工作的全局能力。以后机器若已全局安装同名 `gh-fix-ci`，优先保留仓库
版本，移走或禁用用户目录副本以避免选择器重复；项目自有 Skills 只保留此处一份。

来源、局部适配和验证结果见 [Skills 审计](docs/validation/skills-20261015/report.md)。

## 工程结构

```text
engine/include/ucl/  Search / Evaluator / FeatureExtractor 等公开接口
engine/src/          UCI、Alpha-Beta、手工评估、位置解析
tests/               C++ 单测/Perft、Python UCI/实验工具测试
python/ucl/          match、records、report、training 接口
schemas/             版本化的实验 JSON Schema
experiments/         运行配置与筛选后的结果
scripts/             固定版本外部工具安装
third_party/         chess-library 头文件、许可证与来源
.github/workflows/   macOS/Windows CI
```

详见 [架构](ARCHITECTURE.md)、[路线图](ROADMAP.md)、
[实验规范](EXPERIMENTS.md)、[开发规则](AGENTS.md)。
各阶段实测结果见 [VALIDATION.md](VALIDATION.md)。
UCL 自有代码采用 MIT；第三方依赖保留各自许可证。
棋盘库来源及版本见 [third_party](third_party/README.md)；Python 工具使用
独立安装的 [python-chess](https://github.com/niklasf/python-chess)（GPL-3.0+）。

## R3 数据准备

```sh
.venv/bin/python -m ucl.dataset --output .tools/r3-dataset-new
.venv/bin/python -c 'from ucl.dataset import validate_dataset; validate_dataset("experiments/results/r3-data-v2")'
```

下载固定历史月度库的 2 MiB 前缀，最多取 3000 完整局；不下载整个数据库。
正式保留数据与冻结划分见 `experiments/results/r3-data-v2/manifest.json`，
标签/过滤/去重/训练与比赛预算见 [R3 协议](docs/r3/protocol.md)。
CI 使用三局有来源的 CC0 小棋谱 fixture，无需联网获取训练数据。

R3 特征导出（先提交、重新 configure/build）：

```sh
.venv/bin/python -c 'from ucl.feature_data import export_dataset; export_dataset("experiments/results/r3-data-v2", "build/release/ucl", ".tools/r3-features-new")'
```

`ucl --features` 也接受逐行 FEN，逐行返回版本化 JSON；非法 FEN 退出非零。

R3 模型训练和独立测试（两步分别执行；输出目录和 test marker 均拒绝覆盖）：

```sh
OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python scripts/train_linear.py fit --output experiments/results/r3-model-new
.venv/bin/python scripts/train_linear.py test --output experiments/results/r3-model-new
```

默认使用已冻结的 `r3-data-v2` / `r3-features-v2`。正式结论只引用一次冻结测试，
不按测试结果重训。v1 数据保留历史证据，因八 ply 采样只含白走而在训练前替换。

R3 LinearEvaluator（默认仍为 Handcrafted），UCI 设置顺序：

```text
setoption name ModelSHA256 value 446d18379cfa66e018c4be56218db044339e4be137309c9a17dfbab69874269b
setoption name ModelFile value experiments/results/r3-model-v1/model.txt
setoption name Evaluator value Linear
evalinfo
position startpos
go depth 4
```

`evalinfo` 可核对实际模型；加载失败输出 command rejected 并保留有效配置。
切回使用 `setoption name Evaluator value Handcrafted`。实验 CLI 自动按加载顺序
设置选项并使用绝对路径，保存模型副本和实际 evaluator 身份。

R3 对照实验（先提交、重新 configure/build，输出目录不可复用）：

```sh
.venv/bin/ucl-lab benchmark --config experiments/configs/r3-benchmark.json --output experiments/results/r3-bench-new
.venv/bin/ucl-lab match --config experiments/configs/r3-match.json --output experiments/results/r3-match-new --fastchess .tools/bin/fastchess
.venv/bin/ucl-lab validate experiments/results/r3-bench-new/record.json
.venv/bin/ucl-lab validate experiments/results/r3-match-new/record.json
```

R3 工程与研究结果、冻结身份和限制见 [最终研究报告](docs/r3/final-report.md)。

## R4 数据与开发基准

冻结方案见 [R4协议](docs/r4/protocol.md)，保留R3全部产物。

```sh
.venv/bin/python -m ucl.r4_data acquire --output experiments/results/r4-data-new
.venv/bin/python -m ucl.r4_data validate --output experiments/results/r4-data-v1
.venv/bin/python -c 'from ucl.feature_data import export_dataset; export_dataset("experiments/results/r4-data-v1", "build/release/ucl", "experiments/results/r4-features-v1")'
OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python -m ucl.r4_training --output experiments/results/r4-baselines-v1
```

正式导出/拟合前提交并重新configure/build；输出拒绝覆盖。此fit不计算test指标；
待所有扩展模型与候选选择冻结后统一进行独立测试。

R4扩展导出、开发消融、性能冻结及唯一正式test/match（全部输出拒绝覆盖）：

```sh
.venv/bin/python -c 'from ucl.feature_data import export_dataset; export_dataset("experiments/results/r4-data-v1", "build/release/ucl", "experiments/results/r4-features-v2", "interpretable-v2")'
OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python -m ucl.r4_training --features experiments/results/r4-features-v2 --output experiments/results/r4-models-v1 --expanded
.venv/bin/python -m ucl.r4_experiment prepare
# commit + clean configure/build before benchmarks
.venv/bin/ucl-lab benchmark --config experiments/configs/r4/full-benchmark.json --output experiments/results/r4-benchmarks-v1/full
# likewise refit8/pawn/king; validate/report each retained record
.venv/bin/python -m ucl.r4_experiment freeze
# commit freeze/config, clean configure/build before these once-only operations
OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python -m ucl.r4_analysis --study experiments/results/r4-models-v1 --freeze experiments/results/r4-models-v1/freeze.json
.venv/bin/ucl-lab match --config experiments/configs/r4-match.json --output experiments/results/r4-match-final-20261015 --fastchess .tools/bin/fastchess
.venv/bin/ucl-lab validate experiments/results/r4-match-final-20261015/record.json
.venv/bin/python -m ucl.r4_results experiments/results/r4-match-final-20261015/record.json --output experiments/results/r4-match-final-20261015/analysis.json
```

`pgn_telemetry=true`保留每步PGN nodes/NPS/clock和原始UCI日志；赛后将日志原字节gzip，
同时保存压缩/原字节hash。分析逐引擎核对全部PGN步数与最终ucl_stats覆盖，区分
中断迭代节点和普通info最后完整层。已存在的冻结test/match不得再次执行或覆盖。

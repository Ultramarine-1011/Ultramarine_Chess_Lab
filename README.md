# Ultramarine Chess Lab

个人 UCI 国际象棋研究平台。C++20 实现 Alpha-Beta、QS、TT、PV 排序及手工/线性
评估；Python 负责数据、训练、对弈和统计。默认使用 Handcrafted 评估器。

## 构建与测试

需要 CMake 3.24+、Ninja、C++20 编译器、Python 3.12+。Windows 使用安装了
C++ 工具的 VS Developer PowerShell；macOS 安装 Command Line Tools。

```sh
python -m venv .venv
# macOS: source .venv/bin/activate
# Windows: 下列 python 使用 .venv/Scripts/python.exe
python -m pip install -r requirements.lock
python -m pip install --no-deps -e .
cmake --preset release -DPython3_EXECUTABLE=<虚拟环境python的绝对路径>
cmake --build --preset release --parallel 4
ctest --preset release
```

运行 `build/release/ucl`（Windows 加 `.exe`）。`debug` 和 `sanitize` 分别用于
Debug 与 Clang/GCC ASan/UBSan。CI 保留 macOS/Windows Release/Debug 和 sanitizer。
只编译引擎可使用 `cmake -S . -B build/engine -G Ninja -DBUILD_TESTING=OFF
-DCMAKE_BUILD_TYPE=Release`，再 `cmake --build build/engine`，无需 Python。
棋盘库和模型哈希库已随仓库提供，CMake 不联网下载依赖。

## UCI

```text
uci
isready
position startpos moves e2e4 e7e5
go depth 4
```

收到 `bestmove` 后可发下一局面；`stop` 停止搜索，`quit` 退出。支持 FEN、
`go depth/nodes/movetime`、时钟/增量、`infinite`，搜索期间可响应 `isready`。
选项包括 MoveOverhead、Quiescence、UseTT、PVOrdering、Hash（MiB）和 Evaluator。
标准棋、单搜索线程；无合法走法返回 `bestmove 0000`。

加载线性模型（路径可含空格）：

```text
setoption name ModelSHA256 value 446d18379cfa66e018c4be56218db044339e4be137309c9a17dfbab69874269b
setoption name ModelFile value experiments/results/r3-model-v1/model.txt
setoption name Evaluator value Linear
evalinfo
```

模型文件在加载时校验格式、维度、有限值和哈希；失败保留有效配置。
`--features` / `--features-v2` 按行导出 FEN 特征；`--infer <model> <sha256>` 批量推理。
`--build-info` 显示 configure 时的源码/编译信息；需要刷新时重新 configure/build。

## 日常 Elo 快测

完成上述 Python 依赖安装，并准备好 fastchess（macOS 用
`python scripts/bootstrap_fastchess.py`；Windows 把 `fastchess.exe` 放到
`.tools/bin/` 或 PATH）。Windows 在 Developer PowerShell 中运行，使用
`.venv/Scripts/python.exe`；macOS 激活 `.venv` 后：

```sh
python scripts/elo.py --set-baseline HEAD   # 可选：固定指定提交并缓存 Release 二进制
python scripts/elo.py                      # 128局，2+0.02，4并发
python scripts/elo.py --games 8 --tc 2+0.02 --concurrency 2
```

未设置基准时，首次自动固定当前已提交的 HEAD；后续始终使用保存的完整 SHA。
`--set-baseline <revision>` 只设置/构建基准后退出，不启动比赛。基准按平台、
架构和 SHA 缓存，日常复用；Candidate 每次重新 configure 并增量构建当前工作区，
允许未提交修改，无需预先构建。工具链升级后可删除对应基准缓存并重新运行。

结果在 `.tools/elo/latest/`：终端和 `report.md` 显示 W/D/L、得分率、相对 Elo
及换色配对 bootstrap 95% CI；`games.pgn`、`record.json`、配置和 fastchess
日志保留在同目录。下次快测覆盖 latest；需要保留时自行复制该目录。
独立开发开局集支持 2–512 个偶数局，每个开局换色两局，无 depth/nodes 限制，
150回合仍未结束则裁和。快测仅提供当前设置的描述性比较；不覆盖正式研究报告。

## 探索实验

```sh
python scripts/bootstrap_fastchess.py
ucl-lab match --config experiments/configs/smoke.json --output .tools/smoke --fastchess .tools/bin/fastchess
# 重跑同一探索输出：加 --overwrite
ucl-lab benchmark --config experiments/configs/r2-ablation.json --output .tools/bench
ucl-lab report .tools/bench/record.json
```

Windows 使用 `.venv/Scripts/ucl-lab.exe` 和 `.tools/bin/fastchess.exe`；引擎配置
路径使用 `build/release/ucl.exe`。未提交代码可直接实验，dirty/build 信息照实记录。
`--overwrite` 仅替换未跟踪的探索包；正式包和历史数据不能通过它覆盖。
`report` 已包含验证，需要单独检查时才运行 `ucl-lab validate <record.json>`。

正式研究使用 `--formal`，统计设计与保存要求见 [EXPERIMENTS.md](EXPERIMENTS.md)。
历史版本可用 `python scripts/build_revision.py <revision>` 独立构建并缓存，
`scripts/prepare_comparison.py` 从两个 manifest 生成对比配置。

## 数据与训练

现有数据、模型和结果入口见 [研究进度](ROADMAP.md)。训练与特征导出可使用临时
开发目录，不需要先提交；开发拟合只使用 train/validation，不能按独立 test 调参。

```sh
python -m ucl.dataset --output .tools/r3-data
python -m ucl.r4_data acquire --output .tools/r4-data
python -c "from ucl.feature_data import export_dataset; export_dataset('experiments/results/r3-data-v2', 'build/release/ucl', '.tools/features')"
python scripts/train_linear.py fit --output .tools/model
python -m ucl.r4_training --features experiments/results/r4-features-v2 --output .tools/ablation --expanded
```

R3 训练默认使用已保存的八维数据/特征；R4 扩展训练使用十四维特征。拟合目录可
直接重跑；含正式 test 结果或 R4 候选冻结的目录受保护。独立测试是单独步骤，详见
实验规范。历史重现应检出相应提交；历史协议中的逐阶段审计流程不约束日常开发。

R6目标对齐研究使用同一批新真实局面比较G（棋局结果）、T（固定Stockfish评分）
和M（混合软标签），复用十四维模型及R4优化器。数据/教师、训练与实战入口分别为
`python -X utf8 -m ucl.r6_data --help`、`python -X utf8 -m ucl.r6_training --help`、
`python -X utf8 -m ucl.r6_study --help`；完整命令和教师二进制身份见
[R6复现入口](docs/validation/r6/commands.md)，设计见[R6协议](docs/r6/protocol.md)。
已封存test结果可直接阅读；重复训练或新独立测试使用新的开发目录。
实际结果见[R6最终报告](docs/r6/final-report.md)：M08相对G取得本条件下的实战收益，
尚无优于Handcrafted的充分证据；默认评估器不变。

R5完成了Windows性能研究和四组共1600局正式对弈，见[R5研究报告](docs/r5/final-report.md)。
静态耗时下降31.03%；直接对原版有条件性收益，对Handcrafted仍未改善到可替换默认。
已归档数据可离线重算，无需历史引擎或重跑比赛：

```sh
python -m ucl.r5_analysis --input experiments/results --output .tools/r5-analysis
python docs/r5/generate-report.py
```

第二条从已归档分析JSON生成正式报告；第一条把重算结果写到独立临时目录。

## 导航

- [架构与接口](ARCHITECTURE.md)：引擎、模型格式和 Python 模块边界。
- [实验方法](EXPERIMENTS.md)：探索/正式实验、数据隔离和统计解释。
- [研究进度](ROADMAP.md)：已取得结果与后续研究状态。
- [验证结果](VALIDATION.md)：当前回归与历史证据入口。
- [.agents/skills](.agents/skills)：工程验证、实验分析与 CI 修复的简短提示。

引擎规则依赖见 [third_party](third_party/README.md)。UCL 自有代码为 MIT；
Python 实验使用独立安装的 GPL-3.0+ python-chess。

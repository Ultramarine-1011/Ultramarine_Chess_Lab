# Ultramarine Chess Lab (UCL)

可运行、可比较、可复现的 UCI 国际象棋引擎研究项目。C++20 负责引擎与推理，
Python 负责数据、训练接口、实验和统计。第一轮实现经典基线，不包含 NN/RL。

## 从全新克隆开始：macOS

前置条件：Git、Apple Command Line Tools、Python 3.11+、CMake 3.24+、Ninja。
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

安装 Git、Python 3.11+、CMake 3.24+、Ninja 和 Visual Studio 2022/2026 C++
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
选项 `MoveOverhead`（默认 10ms）；深度上限 128；无参数 `go` 默认深度 5。
无合法走法输出 `bestmove 0000`。搜索期间仍可响应 `isready` 和 `stop`。
首版仅标准国际象棋，不支持 Chess960、ponder、searchmoves、UCI Hash/Threads。

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
第一轮实测结果见 [VALIDATION.md](VALIDATION.md)。
UCL 自有代码采用 MIT；第三方依赖保留各自许可证。
棋盘库来源及版本见 [third_party](third_party/README.md)；Python 工具使用
独立安装的 [python-chess](https://github.com/niklasf/python-chess)（GPL-3.0+）。

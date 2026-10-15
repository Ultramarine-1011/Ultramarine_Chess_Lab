# Windows 实验主机首次环境初始化与工程验证

2026-10-15（Asia/Singapore）。范围仅为 Windows 工具安装、Release 构建、现有
CTest、UCI 和 Python CLI 兼容性；没有启动 R5、正式比赛、benchmark、数据获取、
模型训练命令或已冻结的独立 test。下列 PASS 不代表 Windows 正式研究或棋力验证。

最终默认环境为标准 Visual Studio Build Tools 2026 18.10.4 / MSVC 19.51.36260，
Release CTest 6/6、UCI/CLI 和 fastchess 40/40 均通过。中文 MSVC 的 Ninja
头文件依赖识别需要本机 CMake 前缀修正，详见下方；没有修改引擎算法。

## 首次便携工具链测试身份与结果

实际测试源码：`80616335bdd1455201c13562ced8673d7da9b99f`，configure 时工作树干净。
`build-info.log` 记录 MSVC Release、`dirty=false` 和完整编译参数。测试时的
`build/release/ucl.exe` SHA-256：
`fad406adbbc1ffe04f8ece18e52edb613b8b650708ebf301935026840d2ab74c`。
本次仓库变更仅为此验证记录、日志及显式启用的本机 CMake 诊断前缀修正；引擎、测试、Python、项目 CMakeLists/presets、依赖锁、
ROADMAP 和全部研究产物未修改。提交后重新 configure/build，使本地主机 binary
嵌入最终文档提交身份；以下归档日志仍准确归属于上述实际测试版本。

| 检查 | 实测结果 | 证据 |
| --- | --- | --- |
| CMake Release configure / build | 均退出 0，11 个构建步骤完成 | `configure.log`, `build.log` |
| `ctest --preset release` | 6/6，25.66 秒，退出 0 | `ctest.log` |
| C++ unit / search / perft | 分别 30 / 685 / 14 个 checks 通过 | 本地 `build/release/Testing/Temporary/LastTest.log` |
| Python UCI / experiments / research 测试 | 分别 13 / 10 / 19 个用例通过 | 同上；research 使用现有测试及临时输出，不重复正式冻结 test |
| 独立基础 UCI | uciok、readyok、默认 Handcrafted、depth 4 合法 `b1c3`、将死 `0000`、quit=0 | `basic-uci.log` |
| Python 安装与依赖 | editable 安装成功，`pip check` 退出 0 | `pip-check.log`, `pip-freeze.log` |
| 实验 CLI | 主帮助和四项子命令帮助均退出 0 | `runtime-results.json` |
| CLI 只读 validate / report | 对既有 `r4-telemetry-smoke/record.json` 均退出 0；报告仅输出 stdout | `cli-validate.log`, `cli-report.log` |
| fastchess | 官方 Windows 版启动成功；UCI compliance 40/40，退出 0 | `fastchess-version.log`, `fastchess-compliance.log` |
| 研究文件保护 | 测试前后 219 个文件集合及 SHA-256 逐一完全一致 | `preservation.json` |

## 本机环境与本地配置

- Windows 11 家庭中文版 x64，10.0.26100；AMD Ryzen 9 8940HX，16 核 / 32 线程。
- 复用 Git 2.54.0.windows.1、GitHub CLI 及其现有授权；没有升级无关软件。
- 普通终端的 `python` 是 WindowsApps 占位符，`py -0p` 无已注册解释器；发现
  Anaconda Python 3.13.9 和 Codex 自带 Python 3.12.14。选用后者创建 Windows
  `.venv`，与 CI 的 Python 3.12 系列一致，没有向 base 环境安装项目包。
- `.venv` 安装 `requirements.lock` 全部固定版本及 editable `ucl-lab`；构建工具
  使用与 CI 相同的 CMake 4.4.4、Ninja Python distribution 1.13.2
  （`ninja --version` 为 `1.13.2.git.kitware.jobserver-pipe-1`）。
- 原机没有可发现的 Visual Studio/MSVC 安装。标准 winget 安装
  `Microsoft.VisualStudio.BuildTools` 18.10.4 的尝试返回安装器 1602（取消），
  没有据此声称安装成功。随后使用已检查源码的
  [PortableBuildTools v2.10.2](https://github.com/Data-Oriented-House/PortableBuildTools/tree/v2.10.2)
  从 Microsoft 下载源提取工具至 `.tools/msvc`，CLI 参数为
  `accept_license msvc=14.44.17.14 sdk=26100 target=x64 host=x64 env=none path=<仓库>/.tools/msvc`，退出 0。
  实际 MSVC 19.44.35229，目录 14.44.35207，SDK 10.0.26100.0；`cl.exe` 和
  `link.exe` 的 Microsoft Authenticode 签名均 Valid，见 `msvc-signatures.json`。
  便携工具仅对当前 shell 配置环境，无需管理员安装或修改系统 PATH / 执行策略。
- `.tools/windows-env.ps1` 是本地环境入口，优先通过 vswhere 加载标准安装的
  `Launch-VsDevShell.ps1 -Arch amd64 -HostArch amd64 -SkipAutomaticLocation`，
  找不到标准工具链或显式 `-Portable` 时加载 `.tools/msvc/devcmd.ps1`，并把
  `.venv/Scripts`、`.tools/bin` 加到当前进程 PATH，设置 `PYTHONUTF8=1`。
  这些工具、脚本、包缓存及 `.venv` 均保持 Git ignored，不随此记录提交。
- 已生成 `.tools/windows-smoke.json`：只将原 smoke 配置的两个引擎路径改为
  `build/release/ucl.exe`。现有配置验证器及引擎/开局/fastchess 路径解析通过，
  **未执行该配置，没有新增任何对弈局**；原实验配置原字节保留。

本机后续普通 PowerShell 可运行：

```powershell
cd C:\Ultramarine_Chess_Lab\Ultramarine_Chess_Lab
. .\.tools\windows-env.ps1
cmake --preset release "-DPython3_EXECUTABLE=$PWD/.venv/Scripts/python.exe" "-DCMAKE_PROJECT_INCLUDE=$PWD/docs/validation/windows-init-20261015/windows-msvc-rules.cmake"
cmake --build --preset release --parallel 4
ctest --preset release
.\.venv\Scripts\ucl-lab.exe --help
.\.tools\bin\fastchess.exe --version
```

独立 UCI 的逐条输入输出见 `basic-uci.log`；CLI 及 compliance 的完整实际参数、
退出码在 `runtime-results.json`。compliance 命令是
`.tools/bin/fastchess.exe --compliance <仓库>/build/release/ucl.exe`，不是比赛。

## 标准 VS 安装重试与最终验证

用户随后明确要求重新触发 UAC，并确认允许。相同 winget 命令的重试退出 0，
安装 Visual Studio Build Tools 2026 18.10.4，目录
`C:/Program Files (x86)/Microsoft Visual Studio/18/BuildTools`。
vswhere 确认 `isComplete=true`、`isLaunchable=true`、`isRebootRequired=false`。
实际编译器 MSVC 19.51.36260.0（toolset 14.51.36231），SDK 10.0.26100.0。
两个官方编译/链接程序签名均 Valid，见 `vs-installation-summary.json` 和
`vs-signatures.json`；便携工具链保留于 ignored `.tools`，默认已切换至标准 VS。

本机标准安装仅有中文编译器资源。首次构建虽退出 0，但 `ninja -t deps` 中
八个目标文件的依赖计数全为 0：CMake 4.4.4 将实际 UTF-8 的
`注意: 包含文件:  ` 解码成 CP936 乱码 `娉ㄦ剰: 鍖呭惈鏂囦欢:  `，Ninja 因前缀
不匹配丢失头文件依赖。仅设 VSLANG=1033 无效；早期 make-rules override 在首次
configure 时也未能稳定生效，因此均不算修复验收，原日志保留在本地。

最终修复为本机显式 `CMAKE_PROJECT_INCLUDE`，只在观察到上述精确乱码时替换
`CMAKE_CL_SHOWINCLUDES_PREFIX`，没有调整任何优化参数或算法。
完整 5 行配置归档为 `windows-msvc-rules.cmake`（本机测试使用其原字节副本
`.tools/windows-msvc-rules.cmake`）。使用 `cmake --fresh --preset release` 加上
前述 Python/PROJECT_INCLUDE 参数重建后，八个目标的项目头文件依赖计数分别为
`[2,2,3,4,2,5,5,5]`，包含 evaluator.hpp 和 generated build_info.hpp；随后
`cmake --build --preset release` 返回 `ninja: no work to do.`。
见 `vs-incremental-check.json` 和 `vs-noop-build.log`。这也避免把首次能链接成功
误记为完整增量构建兼容。

最终标准工具链在 `8061633` 加仅文档/证据修改的工作树下测试（build-info 中
`dirty=true`，不伪称 clean）：configure/build 退出 0，CTest **6/6，34.23 秒**；
独立 UCI、所有 CLI 检查和只读历史冒烟包 validate/report、pip check、fastchess
compliance **40/40** 全部通过。对应证据为 `vs-configure-final.log`、
`vs-build-final.log`、`vs-ctest.log`、`vs-build-info.log`、`vs-basic-uci.log`、
`vs-runtime-results.json`、`vs-fastchess-compliance.log`。
该测试 binary SHA-256 为
`04043e854eae20317dda5c71d698bdb6f3e2761a5e684d6fa8bee1703d4ac354`。
测试之后再次实查 219 文件哈希完全不变，`vs-preservation.json` 保留结果。
提交后只需更新 binary 中的文档提交身份；不重跑研究或为文档重复整套测试。

## 安装失败、恢复与限制

最初 `pip install -r requirements.lock cmake==4.4.4 ninja==1.13.2` 在 CMake
下载中 read timeout，退出 2。直接下载也遇到截断及 SSL/metadata IncompleteRead，
下载器拒绝了哈希不符的文件。使用清华 PyPI 镜像断点续传，逐文件按官方 PyPI JSON
的 SHA-256 核验后从本地包缓存安装；没有关闭 TLS 校验，没有修改系统代理或 pip
全局配置。setuptools 84.0.0、typing_extensions 4.16.0 是实际解析的额外依赖，
版本见 `pip-freeze.log`。安装用 `--no-index --find-links <本地缓存>`，并先安装
setuptools，随后 `--no-build-isolation -r requirements.lock` 和
`--no-deps --no-build-isolation -e .`，全部退出 0。原始失败和恢复日志保存在
本机 `.tools/windows-init-20261015/`。依赖安装完成前一次构建尝试因找不到 cmake
未执行；实际构建成功的依据仅是归档的后续 configure/build 和 CTest 日志。

fastchess 使用 [官方 v1.8.2-alpha Windows x86-64 发布包](https://github.com/Disservin/fastchess/releases/tag/v1.8.2-alpha)，
提交 `f618e34540f94f4719ad3817950618dabe441318`，ZIP SHA-256
`007ce550dc809510b34622a1aeb43fd443d40284045bef5c1bc39c8941114143`，
下载后校验一致，安装为 `.tools/bin/fastchess.exe`。它与仓库 bootstrap 固定的
`ebfd64cb7fac80d4822c50b07dca4fe934779d21` 不同；仅确认本机启动与协议可用，
不声称复现正式实验的 fastchess 工具身份。重定向输出时该版本会打印
`Failed to get console mode. Error code: 6`；40 项协议检查及进程退出仍成功，
原警告保留，未修改第三方工具或仓库代码以消除该外部提示。

除上述仅本机 CMake 前缀修正外，没有发现必须修改引擎/Python/测试源码的 Windows
兼容性问题。本地 `.venv`
依赖原 Codex Python 的安装路径，若该运行时移走应重建虚拟环境。Debug、sanitizer、
正式 match 和性能/棋力实验本轮 NOT_RUN。已有历史 Windows CI 通过情况保持其原有
范围；最新被核对的构建 CI 是 `685bf63` 的 Actions #38734978260 五项 success。
本次只提交文档与工程验证日志，使用 `[skip ci]`，不把历史 CI 当作本次测试结果。
Windows 本机工程验证 PASS 不改变历史研究报告中正式 Windows 实验 NOT_RUN 的结论。

工具安装流程参考 [Microsoft MSVC 安装文档](https://learn.microsoft.com/en-us/cpp/overview/acquire-msvc?view=msvc-170)。
本轮完成后停止，不推进 ROADMAP 或 R5。

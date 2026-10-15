# UCL Skills 配置审计（2026-10-15）

范围：仅 Codex Skills 配置与可用性验证；R2 已验收，未启动 R3 或引擎算法开发。
起点 `8a7d450`，工作树干净且与 origin/main 一致；开始时最新代码 CI
[#38700282364](https://github.com/Ultramarine-1011/Ultramarine_Chess_Lab/actions/runs/38700282364)
为 `eee9d44` 的五项 success。仓库没有 PR；检查分支推送使用 Actions run。

## 配置决策与来源

| Skill / 能力 | 决策 | 理由 |
| --- | --- | --- |
| `ucl-engine-validation` | 新建，仓库级 | 选择已有 CTest/Perft/UCI 检查并归档工程验收证据 |
| `ucl-experiment-audit` | 新建，仓库级 | 复用 validate/report，审查实验身份、配对、统计解释和硬件证据 |
| `gh-fix-ci` | 固定版本安装，仓库级 | 已有 macOS/Windows Actions；复用官方日志检查脚本 |
| `skill-creator` / `skill-installer` / `openai-docs` | 保留内置，不再安装 | 已由运行时提供；curated 安装列表未完整反映内置项，不能只据其 installed=false 重装 |
| `jupyter-notebook` | 跳过 | 当前 Python CLI/JSON/Markdown 已覆盖实验工作流；无 `.ipynb` 或已授权的 Notebook 工作 |
| 文档/表格/前端/部署/浏览器/数据库等 | 保留原全局配置，不复制到项目 | 与当前项目 Skills 配置无直接关系；不破坏其他工作的能力 |

安装前检查用户目录、仓库/祖先目录和内置 Skills、当前会话插件目录及触发描述；
未发现同名的三个目标 Skills 或原有项目级配置。文档、PDF、幻灯片、表格的全局
Skills 与插件有功能交集，本轮不通过卸载或全局禁用影响其他任务。项目内只保留
`.agents/skills` 一处来源，没有 `.codex/skills` 副本、用户目录副本、符号链接或
机器绝对路径配置。发现/启用的最终实际状态见 discovery.json（运行时范围）。

`gh-fix-ci` 来源：
[openai/skills@49f948faa9258a0c61caceaf225e179651397431](https://github.com/openai/skills/tree/49f948faa9258a0c61caceaf225e179651397431/skills/.curated/gh-fix-ci)。
通过内置 skill-installer 的 `install-skill-from-github.py --repo openai/skills
--ref 49f948faa9258a0c61caceaf225e179651397431 --path skills/.curated/gh-fix-ci
--dest .agents/skills` 安装。保留许可证及 UI 引用的图标；脚本未修改。
仅在 SKILL.md 添加 UCL integration（已有授权与无 PR 的 SHA/run 路径），并在
default_prompt 中加入 `$gh-fix-ci`。以后更新时先比较固定版本，再保留这两处适配；
不自动追随上游 main。其余两个 Skill 使用内置 skill-creator 初始化与生成 UI 元数据。

发现规则依据 [官方 Skills 文档](https://learn.chatgpt.com/docs/build-skills)：
仓库 `.agents/skills`、自动匹配、显式调用以及同名项不合并。三个 Skill 都保持
默认自动匹配，用描述区分工程验证、统计审计和 CI 故障，不增加额外 MCP 依赖。
安装后在下一轮可用；选择器未刷新时重启应用。

## 验证方法与记录

运行时探针 [probe_discovery.py](probe_discovery.py) 仅调用 `initialize` 和
`skills/list(forceReload=true)`，不建立模型任务或修改配置；从根目录与 tests
子目录检查三个目标均唯一、enabled、scope=repo、路径与默认调用提示正确。
它是本次可复现实测证据，不是额外的引擎/统计验证实现。

本轮手动加载新 Skill 并执行其已有工具路径；未另开模型回合测试隐式路由，
也未把元数据发现结果冒充 Windows 桌面实际调用。命令与输出在本目录留档。

环境问题与处理：

- Homebrew CLI 0.133.0 的 skills/list 报全局 MCP 配置 `writes` 枚举不兼容；
  改用当前桌面应用自带 CLI 0.162.0-alpha.17.2，未改动全局权限配置。
- 系统和项目 Python 均无 PyYAML，创建器 UI 生成首次失败；在忽略目录
  `.tools/skills-audit-20261015/venv` 安装 `PyYAML==6.0.3` 后重试。
  仅作者校验需要此临时依赖，项目 requirements/pyproject 不变。
- 当前没有 PR，官方 PR helper 的无 PR 路径预计返回非零；另外用实际历史失败的
  Actions run 验证其日志读取功能，具体结果见后续验证记录。
- 首次 CMake 命令错误地将 `.venv/bin/python` 符号链接解析为系统解释器，导致
  UCI/experiments 缺少 chess/jsonschema 而失败。改用 README 中虚拟环境原路径，
  重新 configure/build 后 targeted 及完整 Release 通过；没有引擎改动。

## 实际结果

测试版本：`8a7d450` + dirty（本轮 Skills、README、审计及验证记录）。
完整 SHA、宿主、Skills 内容哈希和已有 CI 快照见 [environment.json](environment.json)。

| 验证 | 结果与证据 |
| --- | --- |
| 官方 quick_validate | 三个 Skill 均通过，见 [命令](workflow-commands.json) / [日志](skill-workflows.log) |
| 发现/调用元数据 | 桌面 CLI 从 root/tests 各发现 23 项，其中 3 个 repo、15 个 user、5 个 system；三个目标唯一启用、默认提示含显式调用名，零解析错误，[输出](discovery.json) |
| 旧 CLI 失败 | 完整保存 [错误](discovery-old-cli-error.json)，无全局配置改写 |
| 引用及 UI | 本地 Markdown 链接目标存在，无 TODO；openai.yaml 由官方生成器生成，图标由运行时解析；无额外工具依赖 |
| 引擎工作流 | configure/build、unit/perft 2/2、Release CTest 5/5，[精确命令](engine-retry-commands.json) / [日志](engine-retry.log) |
| 首次解释器误配 | 3/5，两个 Python 测试缺包；保留 [命令](engine-commands.json) / [失败日志](engine.log) |
| 审计工作流 | 三份 R2 正式消融/跨版本基准/版本赛 `validate` 和 `report` 均通过；既有 Python 实验测试 8/8，[命令](workflow-commands.json) / [输出](skill-workflows.log) |
| gh helper | `--help` 成功，无 PR 返回 1 并报告 no pull requests（预期），见工作流日志 |
| 历史 Actions 日志 | 实际调用官方 `analyze_check` 读取旧失败 run #38693291133，status=ok、原 SHA 一致，[结果/片段](gh-historical-failure.json)；未重跑或修复历史代码 |

引擎命令遵循 README；重试使用 `cmake --preset release
-DPython3_EXECUTABLE="$PWD/.venv/bin/python"`、`cmake --build --preset release
--parallel 4`、`ctest --preset release -R '^(unit|perft)$'`、`ctest --preset release`。
审计命令为 `.venv/bin/ucl-lab validate/report experiments/results/<bundle>/record.json`；
三个目录分别是 `r2-ablation-final-20261015`、`r1-r2-benchmark-final-20261015`、
`r1-r2-match-final-20261015`。所有命令逐项保存在 JSON 与日志中。

实际审计结论：720/180 查询包和 16 局配对赛内部一致，13W/3D/0L、配对计数
[0,0,0,3,5]、描述性 bootstrap 区间符合已存结果。结论仍限于原 R2 验收与描述性
统计，不把重复计时或小样本赛转成显著性/Elo 结论。未创建新实验或修改历史产物。

未运行本机 Debug/sanitizer（无 C++ 改动）、Windows 桌面 Skills 调用或用户实验
主机测试，也未验证模型在独立回合中的隐式选择。Git 同步与跨平台文件布局不等同
于 Windows 实验主机验收。后续需要 Notebook 时再按授权配置，不预装训练工具。

## 提交、同步与最终 CI

配置提交 `9606cdb30db76efe7253d8b621fea25344f079b5` 已推送 origin/main。
从该干净提交以 `git clone --no-local` 建立临时独立克隆，执行同一发现探针，
root/tests 三个 Skill 均唯一启用；所有 Skills 文件与已留档 SHA-256 一致，
没有符号链接依赖。克隆命令、探针调用及输出见 [clean-clone.json](clean-clone.json)。
临时克隆测试后移除。这证明 Git 包含所需文件；Windows 桌面调用仍未实机执行。

干净 `9606cdb` 重新 configure/build，Release CTest 5/5，
[命令](clean-release-commands.json) / [日志](clean-release.log) 保留精确参数。
对应 [Actions #38705038767](https://github.com/Ultramarine-1011/Ultramarine_Chess_Lab/actions/runs/38705038767)
五个 job 全 success（macOS/Windows Release/Debug、macOS sanitizer），
Mac Release 包含原有 fastchess smoke；[实际快照](ci.json)。这些是托管 CI 证据，
不宣称用户 Windows 实验主机或 Windows Codex 选择器已经验证。

完成后仅追加本节、VALIDATION.md 与小型证据文件，以文档收尾提交同步，不改变
Skills 内容或工程实现。授权范围已完成，无需启动后续研究阶段。

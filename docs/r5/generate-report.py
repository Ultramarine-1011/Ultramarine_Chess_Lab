"""Generate the R5 Markdown report solely from retained real study packages."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'python'))
from ucl.r5_study import ORIGINAL, MODEL_SHA
from ucl.records import sha256


def load(path):
    return json.loads((ROOT/path).read_text(encoding='utf-8-sig'))


def percent(value): return f'{100*value:.3f}%'
def number(value): return f'{value:.2f}' if isinstance(value,(int,float)) else str(value)
def interval(values, percentage=False):
    return '['+', '.join(percent(v) if percentage else f'{v:.2f}' if isinstance(v,(int,float)) else str(v) for v in values)+']'


def generate():
    analysis=load('experiments/results/r5-analysis-v1/summary.json')
    perf=load('experiments/results/r5-performance-v1/index.json')
    eq=load('experiments/results/r5-equivalence-clean-v1/record.json')
    freeze=load('docs/validation/r5/formal-freeze.json')
    opening=load('experiments/results/r5-openings-v1/manifest.json')
    original=load('docs/validation/r5/original-build.json')
    optimized=load('docs/validation/r5/optimized-build.json')
    groups=analysis['groups']; static=perf['summary']['static']
    gain=1-static['P']['mean_of_block_position_medians_ns']/static['O']['mean_of_block_position_medians_ns']
    d=groups['D']; supports=d['bootstrap']['ci98_75_bonferroni_four'][0]>.5
    leading={
        'above':'本实验支持相同Full14语义的优化实现取得条件性棋力收益。',
        'below':'D组校正区间低于50%，本条件下优化实现的对弈结果为负向，未支持棋力提升。',
        'inconclusive':'本实验未取得经四比较校正后足以支持优化实现提高棋力的证据。'
    }[d['confirmatory_vs_half']]
    node_conclusion={
        'below':'B的校正区间仍低于50%，说明本设置中仅控制节点上限不足以消除Full14劣势。',
        'above':'B的校正区间高于50%，说明等节点预算下的结果有利Full14；这仍不是计算成本的精确因果分解。',
        'inconclusive':'B的校正区间包含50%，本研究不能确认固定节点下Full14仍较弱，也不能据此证明两者等强。'
    }[groups['B']['confirmatory_vs_half']]
    lines=['# R5 评估效率与搜索预算研究', '',
        leading+f'静态评估耗时下降{100*gain:.2f}%，全部1600局按冻结样本完成。',
        f'D组优化版对原版得分{percent(d["statistics"]["score"])}，校正区间'
        f'{interval(d["bootstrap"]["ci98_75_bonferroni_four"],True)}；'
        f'C组对Handcrafted仅得{percent(groups["C"]["statistics"]["score"])}，'
        'C−A探索性配对区间跨0，未证明对共同对手改善。', '',
        '**Handcrafted继续作为默认Evaluator；R4模型/数据/test结果未改动，未训练或实施R6。**', '',
        '## 验收与研究边界', '',
        '| 阶段 | 状态 | 实际证据 |','|---|---|---|',
        '| R5.1 | PASS | Windows clean Original、独立200开局重建、真实时间/节点/调度预检 |',
        '| R5.2 | PASS | clean原/优化48815局面和366搜索查询逐项精确等价 |',
        '| R5.3 | PASS | 三个交替静态块及450搜索查询；原始benchmark-v1包 |',
        '| R5.4 | PASS | A/B/C/D各400局、同200开局、完整PGN/UCI及逐步对应核验 |',
        '| R5.5 | PASS | 从真实包生成配对统计、校正区间、终局审计及本报告；工程验收另见最终CI记录 |', '',
        '工程完成与速度/棋力假设分别判断。没有依据离线BCE或smoke宣布棋力提升。',
        '协议先于正式结果提交：`fcdfef0ff761ea97fcc35dbd7b364ed437454aa0`；',
        '最终配置/分析冻结提交：`97621be5b2b23ff6c71b1e5d22dfad2c3366cd91`。',
        '完整过程、失败、恢复和最终Git/CI见[VALIDATION](../../VALIDATION.md)，',
        '[协议](protocol.md)、[命令与日志索引](../validation/r5/commands.md)。', '',
        '## Windows环境与构建身份', '',
        'Windows 11 26100 / AMD Ryzen 9 8940HX 16核32线程 / 约32GiB物理内存，',
        'ASUS TX Gaming FA608PP；接电100%，原有Turbo电源计划。系统报告HypervisorPresent=true；',
        '这是本机物理主机采集，不是GitHub托管runner。MSVC19.51.36260、CMake4.4.4、',
        'Ninja1.13.2、Python3.12.14。标准工具链和本机中文MSVC头依赖前缀修正均复用，无重装。',
        '每静态块及每正式组前后保留CPU/背景进程/电池/电源快照；ACPI温度查询拒绝访问，',
        '未获取温度或独占机器，因此不能排除调度、散热和桌面负载漂移。没有改变系统电源计划。', '',
        '| 对象 | 完整身份 | SHA-256 |','|---|---|---|',
        f'| Original引擎 | `{ORIGINAL}`, clean | `{original["sha256"]}` |',
        f'| Optimized引擎 | `{freeze["optimized"]}`, clean | `{optimized["sha256"]}` |',
        f'| Frozen Full14 | 原R4 full.txt，实际UCI linear-v2 | `{MODEL_SHA}` |',
        f'| fastchess | 官方v1.8.2-alpha / f618e34540f94f4719ad3817950618dabe441318 | `{freeze["tool_sha256"]}` |',
        f'| 开局EPD | 同一200局面、顺序冻结 | `{freeze["openings_sha256"]}` |', '',
        '两引擎分别由scripts/build_revision.py临时detached worktree独立构建；',
        '同编译器、Release `/DWIN32 /D_WINDOWS /EHsc /O2 /Ob2 /DNDEBUG`，没有fast-math或不同优化参数。',
        '实际UCI evaluator/model身份与fastchess实际setoption逐项核对。Handcrafted始终来自Original。',
        '原二进制留在本机ignored .tools/engines/<SHA>；Git保存完整重建命令、源码提交与binary hash。', '',
        'R4来自Apple A18 Pro/macOS、AppleClang21 `-O3`、电池/桌面负载和不同fastchess开发提交',
        '`ebfd64cb7fac80d4822c50b07dca4fe934779d21`。其35.875%和4.01倍静态成本为历史结果；',
        '**不与本轮Windows原始计时或胜负合并**。相同时控仅提供条件可比性，不是跨硬件复现保证。', '',
        '## 开局与冻结控制', '',
        f'Lichess [CC0标准棋月库](https://database.lichess.org/)2017-09，HTTP206固定前3MiB，',
        f'压缩前缀SHA `{opening["source"]["sha256"]}`，最多4000完整棋局、48MiB解压上限。',
        f'既有合法性/rating>=1500/base>=180秒/Normal/>=32ply过滤后1100局；seed20261016，',
        '按SHA256(seed:game_id)顺序取前200个唯一合法非终局12ply位置。排除R3/R4比赛开局、',
        '保留训练局面精确/颜色镜像、完整源游戏/Site及可重建来源的12ply开局重叠。',
        '没有用评估分数或R5胜负选择开局；PGN/选择清单/EPD和全部排除文件hash已离线重建。',
        '这是月库前缀方便样本，不是整月随机样本；不同棋局仍可能共享玩家和开局家族。',
        'EPD重置先前历史/计数器，两方处理相同，无法恢复开局前重复历史。', '',
        '| 组 | 首引擎（得分视角） | 对手 | 限制 |','|---|---|---|---|',
        '| A | Original Full14 | Handcrafted | 1+0.01秒 |',
        '| B | Original Full14 | Handcrafted | 每着nodes=50000，1000+10秒宽裕clock guard |',
        '| C | Optimized Full14 | Handcrafted | 1+0.01秒 |',
        '| D | Optimized Full14 | Original Full14 | 1+0.01秒 |', '',
        '每组同200开局，每开局先首引擎执白再交换，400局；顺序A→B→C→D。',
        'concurrency=1、单搜索线程、Hash16、QS/TT/PVOrdering=true、MoveOverhead10ms、',
        'maxmoves150，无认输/分数和棋裁决、无SPRT、无按中间结果改变样本或顺序。', '',
        '## 等价优化与正确性', '',
        '对原提取器进行210条交替组件移除微基准：全提取153.46ns、移除王环127.03ns、',
        '移除通路兵141.18ns。该诊断包含编译交互，差值不是可加的组件成本。',
        '最终仅修改extended_features.cpp：预计算2×64通路兵掩码，合并原有计数/兵推进/phase扫描，',
        '直接分配14维vector，避免8维临时向量再resize分配；王环仍用原board.isAttacked。',
        '没有增量搜索状态、新抽象或新搜索算法；Search、TT、QS、PVOrdering、Handcrafted、',
        'LinearEvaluator和冻结模型字节均不变。', '',
        f'clean两实现比较{eq["total_positions"]}个位置：44681全部R4保留位置、2048固定种子随机合法位置、',
        '19个边界以及2067个镜像，覆盖升变/升变额外子力phase>24、易位、吃过路兵、',
        '孤兵/叠兵/同rank阻挡/边文件/裸王/和棋计数/将死逼和。14维名称/顺序/数值/符号',
        '和颜色对称定义保持interpretable-v2；每项还对独立python-chess reference核对。',
        '未取整double经17位输出binary64 round-trip精确比较，最终cp完全一致。',
        '61局面×depth3/4/nodes50000×两实现=366查询，move/score/PV/depth/nodes/qnodes/',
        'TT和ordering counters全部相等；性能研究对应查询也精确一致，未忽略等价选择或非确定性。',
        '诊断dirty包与随后clean独立构建包均保留，正式结论使用clean身份。', '',
        '## 静态成本与搜索吞吐', '',
        '每块10局面×7次×100000调用，块顺序O-P/P-O/O-P；静态先按位置取中位数再平均，',
        '下表为三个块的这些均值再平均，不把重复计时当独立硬件样本。', '',
        '| Full14实现 | ns/call | 同块Handcrafted ns/call | 相对成本 |','|---|---:|---:|---:|']
    for kind,name in [('O','Original'),('P','Optimized')]:
        s=static[kind]; ns=s['mean_of_block_position_medians_ns']; h=s['handcrafted_mean_ns']
        lines.append(f'| {name} | {ns:.4f} | {h:.4f} | {ns/h:.3f}× |')
    ratios=[b['original_over_optimized_ratio'] for b in perf['summary']['static_blocks']]
    lines += ['',f'三个原/优化比为{", ".join(f"{r:.4f}" for r in ratios)}；静态耗时下降{100*gain:.2f}%。',
        'Handcrafted控制也有块间漂移，不能把整个差异解释为无噪声的硬件常数。', '',
        '搜索450查询：10位置×depth3/4/nodes50000×3引擎×5次，固定种子交替引擎顺序、每查询冷TT。',
        '搜索汇总为各位置重复中位数之和；wall包含UCI往返与TT分配。', '',
        '| 引擎 | 限制 | 总节点 | qnodes中位数和 | wall ms | wall NPS |','|---|---|---:|---:|---:|---:|']
    for s in perf['summary']['search']:
        lines.append(f'| {s["engine"]} | {s["limit"]} | {s["median_nodes_sum"]:g} | {s["per_position_median_sums"]["qnodes"]:g} | {s["median_wall_ms_sum"]:.3f} | {s["wall_nps"]:.0f} |')
    lines += ['',
        '两个Full14搜索树逐查询一致，因此其wall差异可以用于本实现性能比较。Handcrafted改变',
        '评估语义和搜索树，不能由不同节点数反推纯推理成本。nodes=50000为每查询上限，',
        '已证mate/终局位置可提前结束；总节点不是10×50000。完整迭代深度、PV、分值、',
        'TT probes/hits/cutoffs/stores和每次耗时均在[搜索测量](../../experiments/results/r5-performance-v1/search/measurements.json)中。', '',
        '## 固定样本对弈统计', '',
        '以开局换色对为观察单位，2000次bootstrap，四组使用同一seed20261016和同一开局索引',
        '重采样。95%为描述性percentile区间；预定四项对50%的判断另用Bonferroni名义98.75%',
        '区间（尾部.00625）。这仍是有限bootstrap、条件开局样本上的近似覆盖，不处理全部',
        '开局家族/日期/玩家/硬件聚类。四组共享开局，不作为独立样本合并。', '',
        '| 组 | W/D/L | 得分率 | 配对95%区间 | 四比较98.75%区间 | 五档配对 |','|---|---|---:|---|---|---|']
    for group,r in groups.items():
        s=r['statistics']; b=r['bootstrap']
        lines.append(f'| {group} | {s["wins"]}/{s["draws"]}/{s["losses"]} | {percent(s["score"])} | {interval(b["ci95"],True)} | {interval(b["ci98_75_bonferroni_four"],True)} | {s["paired_score_counts"]} |')
    lines += ['', '五档为每对0/.5/1/1.5/2分的计数；每组400局、200对。', '',
        '| 组 | Elo-equivalent | 95%区间 | 98.75%区间 | 校正后相对50% |','|---|---:|---|---|---|']
    for group,r in groups.items():
        lines.append(f'| {group} | {number(r["elo_equivalent"])} | {interval(r["elo_ci95"])} | {interval(r["elo_ci98_75"])} | {r["confirmatory_vs_half"]} |')
    lines += ['',
        'Elo-equivalent=400log10(p/(1−p))，区间端点单调变换；只适用于本短时控/开局/硬件条件，',
        '不是通用评级、SPRT结果或跨平台定级。', '',
        '| 配对探索对比 | 得分率差（百分点） | 95%区间（百分点） |','|---|---:|---|']
    for label,r in analysis['exploratory_paired_contrasts'].items():
        lines.append(f'| {label} | {100*r["score"]:.3f} | {interval([100*v for v in r["ci95"]])} |')
    lines += ['',
        'C−A、B−A用同开局差值重采样，仅探索诊断，不增加确认性结论。它们同时改变时钟/树形/',
        '执行次序等条件，不能与D相加为评估语义和成本的精确因果分解。', '',
        '## 终局、节点限制和实际搜索工作', '',
        '| 组 | 自然终局与外部裁和 | 异常完整局 |','|---|---|---:|']
    for group,r in groups.items(): lines.append(f'| {group} | {r["terminations"]} | {r["abnormal_games"]} |')
    unders=groups['B']['node_undershoots']
    reasons={reason:sum(x['reason']==reason for x in unders) for reason in sorted({x['reason'] for x in unders})}
    lines += ['',f'B组全部实际go命令含nodes50000，最终节点均不超过上限；{len(unders)}次提前结束：{reasons}。',
        '每次均检查实际时钟分配仍有余量；不存在时钟提前截断冒充固定节点。未分类提前终止会',
        '使分析失败，本次逐条分类在B/analysis.json中保留。每个PGN着法与trace的根FEN、',
        '完整历史position命令hash、bestmove和合法PV精确对应，无孤立查询或缺失最终stats。', '',
        '语义复核修正了29条派生停止原因：python-chess可申和包含“下一着形成三次重复”，',
        '不能据此把已完成深度128的搜索归为root_draw。现归为max_depth，新增回归覆盖；',
        '仅重算B派生分析，原始棋谱、胜负、区间、逐着记录和搜索计数未变。', '',
        '| 组 | 引擎 | 着法 | 最终nodes | qnodes | 引擎搜索秒 | 聚合NPS | 完成深度中位 |','|---|---|---:|---:|---:|---:|---:|---:|']
    for group,r in groups.items():
        for name,t in r['telemetry']['engines'].items():
            lines.append(f'| {group} | {name} | {t["moves"]} | {t["final_nodes"]} | {t["final_qnodes"]} | {t["engine_elapsed_us"]/1e6:.3f} | {t["aggregate_final_nps"]:.0f} | {t["completed_depth_median"]:g} |')
    lines += ['',
        '最终stats包含中断迭代工作，PGN普通info n=仅最后完整层，两者均保留。实战双方位置和',
        '搜索树不同，聚合NPS/深度仅诊断，不能视为独立静态推理成本或棋力的直接因果量。', '',
        '## 对R4下降原因的证据分层解释', '',
        f'**已测量事实：** 严格等价优化降低本机静态耗时{100*gain:.2f}%，在相同搜索树下改善',
        '固定深度/节点执行时间；这证明原Full14存在可消除的实现成本。',
        f'A得分{percent(groups["A"]["statistics"]["score"])}，B固定节点得分{percent(groups["B"]["statistics"]["score"])}，',
        f'C得分{percent(groups["C"]["statistics"]["score"])}，D直接比较优化/原实现得分{percent(d["statistics"]["score"])}。',
        leading, '',
        '**合理推断：** 固定节点对照减弱每秒吞吐差异，D在相同模型语义下保留时间成本变化。',
        node_conclusion,
        'B相对A的探索性配对变化与静态/同树计时一起用于判断预算机制，不能量化其贡献比例。',
        '相同节点上限下QS比例、分支和每节点静态调用数仍可不同，不能把它等同于相同计算工作。', '',
        '**未验证假设：** R4早期/和棋标签退步、长期棋局结果与搜索局面排序目标不一致、',
        '特征交互和战术补偿不足、便利样本分布偏差，都可能解释剩余问题。R5没有重新训练、',
        '重开R4独立test、做特征因果消融或验证新标签，因此这些仍是待检验解释。', '',
        '## 失败、隔离和版本边界', '',
        '初次预检缺少尚未生成的EPD，在fastchess启动前失败，failed包保留在历史结果中；后续使用新的',
        'v2预检目录。Windows CRLF被Git规范化导致30个R5产物在初次Git blob中字节不同，',
        '随后保留运行时原字节，R5原始证据加-text，未来JSON显式LF；跨平台真实bundle回归通过。',
        '一次ctest未加载env为NOT_RUN，随后绝对路径执行成功；Git Schannel握手失败用单命令',
        'openssl后端恢复，无全局配置更改。失败/修复记录未被后来的PASS覆盖。',
        '正式A启动后，共享主工作树并行进行了全仓库工程简化，用户随后确认并要求继续R5。A继续使用',
        '已加载冻结runner和独立封存binary；全部400局保留。后续在d76ed2c的独立clean',
        'r5-windows-study工作树执行，仅运行缺失的B/C/D组；引擎、模型、工具、配置、开局、',
        '样本均原字节相同，统计方法不变。原outer runner因工作树dirty而停止/失败的状态与',
        '恢复映射保留；没有重跑A、覆盖其他工作的改动或把新研究语义混入正式对弈。',
        '确切恢复提交/路径在recovery-plan.json及VALIDATION中。',
        '交付已整合工程简化提交697737cdbed02f4bf0d29d00e5a15f62966b0f8c：探索实验允许dirty，',
        '正式比较核对实际二进制，保留精简接口和按范围测试。未恢复源码自锁或重复审计系统。',
        '本研究计时/胜负只对应表中的Original和0cf58ac；简化提交另外移除了推理热路径',
        '重复校验，其额外性能影响没有在这四组中测量，不把历史数据当作当前HEAD的计时。', '',
        '## 限制与下一阶段建议', '',
        '本研究是四个固定条件比较，不是严格可加的因果实验。200开局、短1+0.01时控、',
        '固定50000节点、maxmoves150外部裁和、月库便利前缀、共享玩家/开局、桌面调度/',
        '不可读温度、顺序A/B/C/D和工作树隔离事件均限制外推；没有为小Elo效应标定功效。',
        '跨硬件、长时控、其它节点预算、其它训练目标和新算法尚未验证。保留所有负/零/正结果。',
        '下一阶段建议先建立新的独立局面价值标签和评估目标对齐检验，特别关注早期/和棋与',
        '搜索排序；再决定是否研究NNUE或更复杂评估。当前没有NNUE/MCTS/RL的对照证据，',
        '本轮不实现新标签训练、NNUE、MCTS、RL、PVS或LMR。**R5完成后停止。**', '',
        '## 可复核产物', '',
        '- [200开局及来源](../../experiments/results/r5-openings-v1/manifest.json)',
        '- [clean等价证据](../../experiments/results/r5-equivalence-clean-v1/record.json)',
        '- [性能原始包索引](../../experiments/results/r5-performance-v1/index.json)',
        '- [四组统计与逐步核验](../../experiments/results/r5-analysis-v1/summary.json)',
        '- [A原始记录](../../experiments/results/r5-match-a-v1/record.json)、[B](../../experiments/results/r5-match-b-v1/record.json)、[C](../../experiments/results/r5-match-c-v1/record.json)、[D](../../experiments/results/r5-match-d-v1/record.json)',
        '- [正式研究身份记录](../validation/r5/formal-freeze.json)',
        '- [GitHub Actions及关键命令](../validation/r5/commands.md)', '',
        '报告由docs/r5/generate-report.py从保留JSON自动生成；未手改原始胜负或统计。', '']
    target=ROOT/'docs/r5/final-report.md'; target.write_text('\n'.join(lines),encoding='utf-8',newline='\n')
    return {'path':str(target),'sha256':sha256(target),'direct_comparison_supports_conditional_gain':supports}


if __name__=='__main__': print(json.dumps(generate(),ensure_ascii=False,indent=2))

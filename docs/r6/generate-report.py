"""Build the R6 report from the completed, retained experimental records."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'python'))
from ucl.r4_features import NAMES
from ucl.r5_analysis import bootstrap


def load(path):
    return json.loads((ROOT/path).read_text(encoding='utf-8-sig'))


def pct(value):
    return f'{value*100:.3f}%'


def ci(values, percent=False):
    return '['+', '.join(pct(v) if percent else f'{v:.6f}' for v in values)+']'


def generate():
    base = 'experiments/results/'
    selection = load(base+'r6-models-v1/selection.json')
    test = load(base+'r6-models-v1/test-results.json')
    freeze = load(base+'r6-models-v1/freeze.json')
    verification = load(base+'r6-models-v1/verification.json')
    diag = load(base+'r6-data-v1/diagnostics.json')
    analysis = load(base+'r6-analysis-v1/summary.json')
    groups = analysis['groups']
    candidate = selection['candidate']
    c = groups['C']
    time_node = bootstrap([a-b for a, b in zip(groups['C']['paired_means'], groups['D']['paired_means'], strict=True)])
    conclusion = {'above': '在本条件下支持混合监督相对 G 的棋力改善',
                  'below': '在本条件下显示混合监督相对 G 的棋力退步',
                  'inconclusive': '未获得混合监督相对 G 改善棋力的充分证据'}[c['confirmatory_vs_half']]
    lines = ['# R6 评估目标对齐研究', '',
             f'**{conclusion}。** 冻结候选为 {candidate}（α=0.8）。教师/混合监督降低了教师评分误差，',
             '共同独立 test 未观察到可靠的静态着法排序改善；该单步代理没有检出实战中的收益。',
             f'C 组 {pct(c["bootstrap"]["score"])}，配对95%区间 {ci(c["bootstrap"]["ci95"], True)}。',
             '**Handcrafted 继续默认；R3–R5 已封存数据、模型和结论不变。R6 完成后停止。**', '',
             '## 完成范围与预先固定的比较', '',
             '| 阶段 | 执行状态 | 依据 |', '|---|---|---|',
             '| R6.1 数据/教师 | PASS | 真实数据重建、评分视角核对和256局面预检 |',
             '| R6.2 训练 | PASS | 同数据20次拟合均收敛，四模型重新拟合字节一致 |',
             '| R6.3 独立离线测试 | PASS | validation选模，冻结后一次test；没有据test调参 |',
             '| R6.4 实战 | PASS | 四组各400局、200开局换色与逐着UCI核验 |',
             '| R6.5 总结 | PASS | 本报告和原始证据；工程/CI见验证入口 |', '',
             '[协议](protocol.md)先于数据和结果提交（e3888f3）；实现/选模为0403a9d，',
             '模型、分析代码和正式配置在1ca065a冻结。执行状态与研究假设是否成立分别判断。',
             'C 是唯一确认性棋力对比，双侧95%配对区间；A/B/D和离线分层为探索性。',
             '没有按得分追加、截断、换模型或改变固定样本。', '',
             '## 数据与教师口径', '',
             '[Lichess CC0月库](https://database.lichess.org/)2018-01..04每月只取首3MiB压缩前缀，',
             '每源最多4000完整局/48MiB解压。2018-05另取同样上限，用于200个独立12ply开局。',
             '复用原过滤、最多8局面/局和7ply间距；整局划分，跨集合精确/颜色镜像去重。',
             '排除旧来源游戏/Site、旧位置和比赛开局；新开局还排除全部新来源游戏及其12ply位置。', '',
             '| 划分 | 局 | 局面 | 来源 | 和棋局 |', '|---|---:|---:|---|---:|']
    for split in ('train', 'validation', 'test'):
        d = diag['splits'][split]
        lines.append(f'| {split} | {d["games"]} | {d["positions"]} | {", ".join(d["months"])} | {d["game_results"].get("1/2-1/2",0)} |')
    lines += ['', f'严格时间分离={diag["strict_temporal_separation"]}；玩家重叠 {diag["player_overlap"]}。',
              '这些是月库前缀便利样本，覆盖窄时间片；整局聚类仍不能消除重复玩家/开局家族相关性。',
              '独立test为未来窗口，比赛开局来自另一窗口；FEN均无法恢复此前重复历史。', '',
              '[Stockfish 17.1官方发布](https://github.com/official-stockfish/Stockfish/releases/tag/sf_17.1)',
              'Windows AVX2、单线程、Hash16、每查询冷哈希、请求20000节点、MultiPV1，未使用表库。',
              f'本体局面有 {verification["teacher_kinds"]["cp"]} 个cp评分、{verification["teacher_kinds"]["mate"]} 个mate评分；',
              f'实际最终节点共 {verification["actual_final_nodes_sum"]}。深度[min,median,max]={verification["depth_quantiles"]}。',
              '保存最后一个无界限标志的精确迭代评分及最终节点；缺失/异常评分使标注失败，不能填零。',
              'STM评分显式转白方视角，逐条核对；mate保留独立字段，终局采用明确胜/和/负。',
              '256个真实训练局面先打通特征、评分、拟合及C++推理，8个冷哈希查询复现一致，才扩大。', '',
              '教师软目标固定为 sigmoid(clip(SF白方cp,−2000,2000)/400)，mate映射1/0。',
              '[Stockfish评分说明](https://official-stockfish.github.io/docs/stockfish-wiki/Stockfish-FAQ.html#interpretation-of-the-stockfish-evaluation)',
              '描述其归一化尺度；这里的sigmoid是固定建模约定，不是官方WDL概率，也不代表SF cp与UCL cp等价。',
              '教师搜索本身有预算误差；使用外部教师的NNUE不等于在UCL中实现NNUE。', '',
              '## 同容量训练与 validation 选择', '',
              'G/T/M使用完全相同的14000训练位置、14维特征、整局权重、train-only RMS、零截距、',
              'R4 BCE+L2优化器和部署格式。lambda=.0001/.001/.01/.1/1；各目标按自己的validation',
              '目标BCE选lambda。M只用α=.5/.8。不同目标的原始训练loss不作棋力比较。', '',
              '| 模型 | λ | validation结果BCE | 教师BCE | 截断cp MAE | 清晰分差排序 |',
              '|---|---:|---:|---:|---:|---:|']
    for n, m in selection['models'].items():
        v = m['validation']
        lines.append(f'| {n} | {m.get("lambda","—")} | {v["game_bce"]:.6f} | {v["teacher_bce"]:.6f} | {v["cp_mae"]:.3f} | {pct(m["ranking"]["primary_accuracy"])} |')
    lines += ['', '排序取128个预定validation根局面，对每个合法候选着法的实际子局面独立标注，',
              '统一转换到根走棋方视角。比较同一批子局面静态评分，不用根评分充当着法价值。',
              '主指标为教师分差≥100的候选对准确率，静态打平计.5，先位置再整局等权。',
              'mate/终局仅以±100000作排序哨兵，非普通cp误差；无合格对的位置明确排除。',
              f'validation有{selection["models"]["G"]["ranking"]["eligible_positions"]}/128个合格根位置、{selection["models"]["G"]["ranking"]["clear_pairs"]}个清晰分差对。',
              f'M08在T/M05/M08中主指标最高，因此冻结；G略高也没有改换目标或重调候选。', '',
              '| 特征 | G | T | M08 |', '|---|---:|---:|---:|']
    for i, name in enumerate(NAMES):
        lines.append('| '+name+' | '+' | '.join(f'{selection["models"][n]["weights"][i]:.4f}' for n in ('G', 'T', 'M08'))+' |')
    lines += ['', '四个部署文件独立重拟合字节一致；全部23998位置×4模型的C++取整与走棋方分数精确一致。', '',
              '## 新独立 test', '',
              '| 模型 | 结果BCE | 结果Brier | 教师BCE | 教师cp MAE/RMSE | 清晰分差排序 |',
              '|---|---:|---:|---:|---:|---:|']
    for n, m in test['models'].items():
        lines.append(f'| {n} | {m["game_bce"]:.6f} | {m["game_brier"]:.6f} | {m["teacher_bce"]:.6f} | {m["cp_mae"]:.3f}/{m["cp_rmse"]:.3f} | {pct(test["ranking"][n]["primary_accuracy"])} |')
    lines += ['', 'cp误差只用非mate，双方都截断到±2000；是教师尺度一致性诊断，不是精确真实价值误差。',
              f'test有{test["ranking"]["G"]["eligible_positions"]}/128个合格根位置、{test["ranking"]["G"]["clear_pairs"]}个清晰分差对。',
              'R4Full14一行是在这批新数据上的冻结模型参考，没有重算或改写旧独立test。', '',
              '| M08−G，整局聚类描述区间 | 差值 | 95%区间 | 游戏簇 |', '|---|---:|---|---:|']
    for k, v in test['candidate_minus_G'].items():
        lines.append(f'| {k} | {v["difference"]:.6f} | {ci(v["ci95"])} | {v["games"]} |')
    lines += ['', '混合监督可靠降低本样本教师误差，但结果BCE较G退步；排序差值区间包含0，点估计略差。',
              '离线各区间是描述性、并未对所有指标进行家族确认性判断。',
              '开/中/残局按子力phase分层，另保留ply16–40、白黑走棋方与和棋样本。', '',
              '| test分层 | 游戏簇/局面 | G结果BCE | M08结果BCE | M08教师cp MAE |',
              '|---|---:|---:|---:|---:|']
    for name, ms in test['strata'].items():
        g, m = ms['G'], ms['M08']
        lines.append(f'| {name} | {g["games"]}/{g["positions"]} | {g["game_bce"]:.6f} | {m["game_bce"]:.6f} | {m["cp_mae"]:.3f} |')
    lines += ['', 'M08在早期、子力较全和和棋样本的结果BCE改善，代价是中残局结果预测退步；',
              '这些是未校正的分层诊断，没有据此重新选模。',
              '完整分层和十档校准均值在[test-results.json](../../experiments/results/r6-models-v1/test-results.json)，',
              '不以总体改善替代分层证据，也不把材料phase直接等同实际开局阶段。', '',
              '## 推理成本与实际搜索', '',
              '同一Windows Ryzen9 8940HX、MSVC19.51 Release、单搜索线程。R2十位置，',
              'depth4/50000节点各三次固定种子顺序；静态七次交替，每位置每模型100000调用。',
              '静态按逐位置中位数的均值，搜索按逐位置重复中位数求和；这些是描述计时。', '',
              '| 模型 | 静态ns/次 | 同批手工ns/次 |', '|---|---:|---:|']
    for n in ('G', 'T', 'M08'):
        perf = load(base+f'r6-performance-v1/static-{n}/record.json')['tools']['static_evaluation']['summary']
        lines.append(f'| {n} | {perf["mean_position_median_linear_ns"]:.3f} | {perf["mean_position_median_handcrafted_ns"]:.3f} |')
    lines += ['', '| 模型/限制 | 节点 | wall ms | wall NPS |', '|---|---:|---:|---:|']
    for r in load(base+'r6-performance-v1/benchmark/record.json')['summary']:
        lines.append(f'| {r["engine"]}/{r["limit"]} | {r["median_nodes_sum"]:.0f} | {r["median_wall_ms_sum"]:.3f} | {r["wall_nps"]:.0f} |')
    lines += ['', '补充共同validation成本对照：正式赛结束后，按原排序样本的固定hash顺序取前10个',
              '真实validation根局面，执行相同静态/搜索测量。没有按比赛或test结果挑位置；',
              '这批是事后探索性补测，未用于候选选择，不能与前一批原始计时直接合并。', '',
              '| validation模型 | 静态ns/次 | 同批手工ns/次 |', '|---|---:|---:|']
    for n in ('G', 'T', 'M08'):
        perf = load(base+f'r6-validation-performance-v1/validation-static-{n}/record.json')['tools']['static_evaluation']['summary']
        lines.append(f'| {n} | {perf["mean_position_median_linear_ns"]:.3f} | {perf["mean_position_median_handcrafted_ns"]:.3f} |')
    lines += ['', '| validation模型/限制 | 节点 | wall ms | wall NPS |', '|---|---:|---:|---:|']
    for r in load(base+'r6-validation-performance-v1/validation-search/record.json')['summary']:
        lines.append(f'| {r["engine"]}/{r["limit"]} | {r["median_nodes_sum"]:.0f} | {r["median_wall_ms_sum"]:.3f} | {r["wall_nps"]:.0f} |')
    lines += ['', '改变目标会改变评分尺度、搜索树、剪枝和QS工作；不同模型的NPS/节点变化不能单独认定纯推理成本。',
              '没有更改搜索或特征。温度传感器不可读，保留各组前后电源/负载快照，不能排除调度/散热漂移。', '',
              '## 真实棋力：固定时间与节点', '',
              '同200独立开局换色；每组400局，A→B→C→D串行；Hash16、QS/TT/PV=true、',
              'MoveOverhead10ms、maxmoves150，无认输/分数裁和/SPRT。A/B/C为1+0.01秒，',
              'D为每着50000节点，1000+10秒时钟保护。8局流程预检只验证协议和预算。', '',
              '| 组/首引擎对手 | W/D/L | 得分 | 配对95%区间 | 条件Elo等效 | 解释 |',
              '|---|---|---:|---|---:|---|']
    opponents = {'A': 'G vs Handcrafted', 'B': 'M08 vs Handcrafted', 'C': 'M08 vs G，时间', 'D': 'M08 vs G，节点'}
    for group, r in groups.items():
        st = r['statistics']
        # Existing report statistics retain unambiguous explicit W/D/L keys.
        lines.append(f'| {group} {opponents[group]} | {st["wins"]}/{st["draws"]}/{st["losses"]} | {pct(r["bootstrap"]["score"])} | {ci(r["bootstrap"]["ci95"],True)} | {r["elo_equivalent"]:.2f} | {r["confirmatory_vs_half"]} |')
    lines += ['', 'C组预定确认性区间全部高于50%，支持M08相对同数据G的条件性实战改善。',
              'A/B对Handcrafted的区间均包含50%，没有证明G或M08胜过默认评估器。',
              'D点估计同向且描述区间高于50%，但它按预定仅作探索性证据。',
              f'事后探索性同开局配对C−D差值为{100*time_node["score"]:.3f}个百分点，',
              f'95%区间[{100*time_node["ci95"][0]:.3f}, {100*time_node["ci95"][1]:.3f}]个百分点；',
              '没有可靠的时间/节点条件差异证据，亦未作新的确认性判断。', '',
              '按200开局配对bootstrap2000次，seed20261016。C为唯一确认性判断，其余三组探索性；',
              '不把跨条件差值相加为速度与语义的因果贡献。Elo等效只适用于本时控/开局/硬件，非通用定级。', '',
              '| 组 | 终局分类 | 异常完整局 |', '|---|---|---:|']
    for group, r in groups.items():
        lines.append(f'| {group} | {r["terminations"]} | {r["abnormal_games"]} |')
    lines += ['', f'D中提前停止查询 {len(groups["D"]["node_undershoots"])} 条，逐条分类记录在D/analysis.json。',
              '实际go含nodes50000、计数不超过上限，时钟有余量；mate/root-draw/max-depth以实际状态分类。',
              '每个PGN着法与根FEN/完整position历史hash/bestmove/合法PV/final stats对应，无缺失或孤立查询。',
              '完整逐着计数保留在moves.jsonl.gz；普通info最后完成层与最终统计的口径分开。', '',
              '| 组 | 引擎 | 着法 | 最终节点 | qnodes | 搜索秒 | 聚合NPS | 深度中位 |',
              '|---|---|---:|---:|---:|---:|---:|---:|']
    for group, r in groups.items():
        for name, e in r['telemetry']['engines'].items():
            lines.append(f'| {group} | {name} | {e["moves"]} | {e["final_nodes"]} | {e["final_qnodes"]} | {e["engine_elapsed_us"]/1e6:.3f} | {e["aggregate_final_nps"]:.0f} | {e["completed_depth_median"]} |')
    lines += ['',
              '## 解释与下一阶段', '',
              '1. 教师/混合监督改善对教师搜索输出的拟合；G在结果预测上更好。这说明监督目标确实改变拟合方向。',
              '2. 教师误差降低没有转化为本批合法候选着法的静态排序提升，但C组支持M08相对G的实战改善。',
              '   这说明当前单步排序代理不足以替代真实搜索对弈；尚未证明M08优于Handcrafted。',
              f'3. 时间C得分{pct(groups["C"]["bootstrap"]["score"])}，节点D得分{pct(groups["D"]["bootstrap"]["score"])}；',
              '   两种预算的点估计方向一致，事后配对差值区间含0，不能认定存在可靠的条件差异。',
              '   D仅探索性，不能把点估计差异归因为单一机制。',
              '4. 同数据同结构的G与M08是目标干预对照；相对历史R4还同时改变了数据窗口、样本量、',
              '   平台和评估实现成本。新数据上G与旧Full14的离线差异不能识别数据本身的因果贡献，',
              '   没有进行旧/新数据×旧/新目标的完整交叉干预。',
              '5. 下一步优先研究搜索实际叶节点/安静局面的标签与数据覆盖，以及静态特征对战术补偿的表示能力。',
              '   本研究没有证明更强教师、更复杂NNUE或新搜索算法必然有益；应先用同预算对照辨别数据/目标',
              '   和表示限制，再决定NNUE。当前没有为MCTS/RL或搜索算法改动提供独立证据。', '',
              '局限：单一教师和20000节点、固定sigmoid/截断、单一线性容量、128根排序样本、',
              '月库便利前缀和重复玩家、200开局的短时控/节点比赛、顺序执行及不可控桌面负载。',
              '排序指标包含大量战术上较差的合法着法，并不等同搜索实际访问的叶节点分布。',
              '对小Elo变化功效有限；条件区间包含50%不代表等强。没有用负结果继续调参或追加对局。', '',
              '## 证据与复现', '',
              f'- 冻结引擎 `{freeze["engine_revision"]}`，SHA256 `{freeze["engine_sha256"]}`。',
              f'- G `{freeze["models"]["G"]}`；M08 `{freeze["models"]["M08"]}`。',
              '- [数据manifest](../../experiments/results/r6-data-v1/manifest.json)、[教师发布身份](../../experiments/results/r6-preflight-v1/teacher-release.json)。',
              '- [拟合/选择](../../experiments/results/r6-models-v1/selection.json)、[冻结](../../experiments/results/r6-models-v1/freeze.json)、[一次test](../../experiments/results/r6-models-v1/test-results.json)。',
              '- [四组原始比赛](../../experiments/results/r6-matches-v1/A/record.json)、[全部分析](../../experiments/results/r6-analysis-v1/summary.json)。',
              '- [完整复现命令、故障/恢复与工程日志](../validation/r6/commands.md)。',
              '本报告由generate-report.py读取实际完成产物生成，不能代替原始记录或扩展其证据范围。', '']
    return '\n'.join(lines)


if __name__ == '__main__':
    (ROOT/'docs/r6/final-report.md').write_text(generate(), encoding='utf-8', newline='\n')

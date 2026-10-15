"""Render research figures from frozen results; no fitting or resampling."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
import numpy as np

ROOT=Path.cwd();out=ROOT/'docs/r4/figures';out.mkdir(parents=True,exist_ok=True)
t=json.loads((ROOT/'experiments/results/r4-models-v1/test-results.json').read_text())
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False,'savefig.dpi':180,'svg.hashsalt':'ucl-r4'})
fig,axes=plt.subplots(1,2,figsize=(12,5.8),layout='constrained')
groups=[['calibration - handcrafted','frozen_r3 - handcrafted','refit8 - handcrafted','full - handcrafted'],
        ['refit8 - calibration','pawn - refit8','king - refit8','full - pawn','full - king']]
for ax,names,title in zip(axes,groups,['Calibration and temporal generalization','Prespecified feature-group contrasts']):
    for i,name in enumerate(names):
        m=t['contrasts'][name]['bce'];value=m['difference'];lo,hi=m['ci95']
        if ax is axes[1]:
            a,b=m['ci99'];ax.plot([a,b],[i,i],color='#aab7c5',lw=4,label='99% Bonferroni family' if i==0 else None)
        ax.errorbar(value,i,xerr=[[value-lo],[hi-value]],fmt='o',color='#176b87',capsize=4,label='95% game bootstrap' if i==0 else None)
    ax.axvline(0,color='#444',lw=1,ls='--');ax.set_yticks(range(len(names)),[n.replace('_',' ') for n in names]);ax.invert_yaxis()
    ax.set_xlabel('Difference in equal-game BCE (negative favors first model)');ax.set_title(title);ax.grid(axis='x',alpha=.2);ax.xaxis.set_major_locator(MaxNLocator(5));ax.legend(loc='upper center',bbox_to_anchor=(.5,-.2),fontsize=8,ncol=2 if ax is axes[1] else 1)
fig.suptitle('Independent temporal test: 2,173 games / 14,570 positions',fontsize=14)
fig.savefig(out/'offline-ablation.png');fig.savefig(out/'offline-ablation.svg',metadata={'Date':None});plt.close(fig)

study=json.loads((ROOT/'experiments/results/r4-study-final-20261015/record.json').read_text());r=study['results']
names=['refit8','pawn','king','full'];static=[];wall=[];nodes=[]
for name in names:
    b=json.loads((ROOT/f'experiments/results/r4-benchmarks-v1/{name}/record.json').read_text())
    s=b['tools']['static_evaluation']['summary'];static.append(s['mean_position_median_linear_ns']/s['mean_position_median_handcrafted_ns'])
    rows=[x for x in b['summary'] if x['limit']=={'depth':4}];candidate=next(x for x in rows if x['engine']==name);base=next(x for x in rows if x['engine']=='Handcrafted')
    wall.append(candidate['median_wall_ms_sum']/base['median_wall_ms_sum']);nodes.append(candidate['median_nodes_sum']/base['median_nodes_sum'])
fig,axes=plt.subplots(1,2,figsize=(12,4.6),layout='constrained');x=np.arange(4);width=.25
for values,offset,label,color in ((static,-width,'Static cost','#176b87'),(wall,0,'Depth4 wall','#73a5a5'),(nodes,width,'Depth4 nodes','#b9ced3')):
    axes[0].bar(x+offset,values,width,label=label,color=color)
axes[0].axhline(1,color='#555',lw=1,ls='--');axes[0].set_xticks(x,names);axes[0].set_ylabel('Ratio to same-batch Handcrafted');axes[0].set_title('Frozen development performance');axes[0].legend(fontsize=9)
p=r['score'];lo,hi=r['score_ci95_paired_bootstrap'];axes[1].errorbar([p*100],[0],xerr=[[(p-lo)*100],[(hi-p)*100]],fmt='o',capsize=6,color='#176b87',ms=9)
axes[1].axvline(50,color='#555',ls='--');axes[1].set_xlim(0,100);axes[1].set_ylim(-1,1);axes[1].set_yticks([0],['Full14 vs\nHandcrafted']);axes[1].set_xlabel('Paired score (%) with descriptive 95% bootstrap interval');axes[1].set_title(f"Fixed 400 games / 200 opening pairs\n{r['wins']} W / {r['draws']} D / {r['losses']} L")
axes[1].text(p*100,.34,f'{p*100:.3f}% [{lo*100:.3f}, {hi*100:.3f}]',ha='center');axes[1].grid(axis='x',alpha=.2)
fig.suptitle('Prediction, computation and playing strength are separate outcomes',fontsize=14)
fig.savefig(out/'cost-and-match.png');fig.savefig(out/'cost-and-match.svg',metadata={'Date':None});plt.close(fig)
print('Rendered two figures from frozen JSON only')

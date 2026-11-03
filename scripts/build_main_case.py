"""Build shareable case and transparent pilot reports from retained, frozen artifacts."""
from __future__ import annotations
import hashlib, html, json, math, sys, zipfile
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'.vendor'));sys.path.insert(0,str(ROOT))
PILOT=ROOT/'evaluation/host-pilot-20261018'
OUT=ROOT/'研究成果/美国乘用车主案例';FIG=OUT/'figures'
READ=lambda name:json.loads((PILOT/name).read_text(encoding='utf-8'))
NAMES={'KOR':'韩国','MEX':'墨西哥','DEU':'德国','GBR':'英国','CAN':'加拿大','JPN':'日本','CHN':'中国'}
ORDER=['KOR','MEX','DEU','GBR','CAN','JPN','CHN']
E=html.escape

STYLE='''body{font:15px/1.95 "Microsoft YaHei",system-ui,sans-serif;color:#24443a;background:#f7f8f2;margin:0}main{max-width:1100px;margin:35px auto;background:#fffefb;border:1px solid #dfe6d7;padding:44px;border-radius:10px}h1{font-size:29px;line-height:1.6}h2{font-size:20px;border-bottom:1px solid #e1e8d8;padding-bottom:9px;margin-top:38px}h3{font-size:16px}a{color:#287865}small,.muted{color:#7c8b71;font-size:12px}p{margin:12px 0}figure{margin:22px 0}img{width:100%;height:auto}figcaption{font-size:12px;color:#7c8b71;margin-top:8px}.note{background:#f0f4e8;border-left:4px solid #5c8865;padding:15px 20px;margin:20px 0}.warning{background:#fbf3e5;border-left-color:#bf9665}.scroll{overflow-x:auto}table{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums;font-size:13px}th,td{padding:10px;border-bottom:1px solid #e6ecdf;text-align:right}th:first-child,td:first-child{text-align:left}th{background:#f3f6ec}details{padding:12px 0;border-bottom:1px solid #e6ecdf}summary{cursor:pointer;font-size:13px}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px;background:#f7f9f2;padding:14px}.refs{font-size:12px;overflow-wrap:anywhere}.tag{display:inline-block;padding:3px 9px;font-size:11px;background:#e8efdf;color:#64804f;border-radius:4px;margin-right:8px}.response{white-space:pre-wrap}.check{color:#37785b}@media(max-width:650px){main{padding:22px;margin:0;border-radius:0}h1{font-size:23px}table{font-size:11px}td,th{padding:7px}.note{padding:12px}}@media print{body{background:white}main{margin:0;border:0;padding:10px}details{break-inside:avoid}figure{break-inside:avoid}.scroll{overflow:visible}}'''

def page(title,body):return f'<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="icon" href="data:,"><title>{E(title)}</title><style>{STYLE}</style><main>{body}</main></html>'

def ref_html(citations):
    return ' '.join(f'<a href="主案例分析报告.html#{E(ref.replace(":","-"))}">{E(ref)}</a>' for ref in citations)

def charts(analyses):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib import font_manager
    from matplotlib.colors import LinearSegmentedColormap,TwoSlopeNorm
    font=Path('C:/Windows/Fonts/msyh.ttc')
    if font.exists():
        font_manager.fontManager.addfont(str(font));plt.rcParams['font.family']=font_manager.FontProperties(fname=str(font)).get_name()
    plt.rcParams.update({'axes.unicode_minus':False,'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'svg.fonttype':'none','axes.labelcolor':'#365544','text.color':'#365544','axes.edgecolor':'#b7c7ac'})
    main=analyses['main'];partners={p['code']:p for p in main['partners']}
    def finish(fig,name):
        fig.set_facecolor('#fffefb');fig.tight_layout(pad=2)
        for suffix in ['png','svg']:fig.savefig(FIG/f'{name}.{suffix}',dpi=220,bbox_inches='tight',facecolor=fig.get_facecolor())
        plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(12,4.5));ax=axes[0]
    ax.plot([x['year'] for x in main['series']],[x['values']['USA']/1e8 for x in main['series']],marker='o',color='#2d806b',lw=2.5)
    ax.set(title='美国HS 8703进口金额',ylabel='亿美元',xlabel='年度');ax.set_xticks([2019,2020,2021,2022,2023]);ax.grid(axis='y',alpha=.15)
    order=['MEX','JPN','CAN','KOR','DEU','GBR','CHN'];x=list(range(len(order)));ax=axes[1]
    ax.bar([v-.18 for v in x],[partners[c]['share0'] for c in order],width=.35,color='#a8bfa0',label='2019')
    ax.bar([v+.18 for v in x],[partners[c]['share1'] for c in order],width=.35,color='#2d806b',label='2023')
    ax.set_xticks(x,[NAMES[c] for c in order],rotation=30);ax.set(title='主要伙伴在美国进口总额中的份额',ylabel='%');ax.legend(frameon=False);ax.grid(axis='y',alpha=.12)
    finish(fig,'01-金额与份额')
    fig,ax=plt.subplots(figsize=(11,5.6));y=list(range(len(ORDER)))
    ax.barh([v-.18 for v in y],[partners[c]['market_component']/1e8 for c in ORDER],height=.3,color='#6c9d82',label='市场规模变化分量')
    ax.barh([v+.18 for v in y],[partners[c]['share_component']/1e8 for c in ORDER],height=.3,color='#c79469',label='供应份额变化分量')
    ax.scatter([partners[c]['delta']/1e8 for c in ORDER],y,color='#233f36',marker='D',s=29,label='金额净变化',zorder=4)
    ax.axvline(0,color='#a9b99c',lw=.9);ax.set_yticks(y,[NAMES[c] for c in ORDER]);ax.invert_yaxis();ax.set(title='2019—2023供应金额变化的对称分解',xlabel='亿美元；两项分量之和等于净变化');ax.legend(frameon=False,loc='lower right');ax.grid(axis='x',alpha=.12)
    finish(fig,'02-对称分解')
    keys=list(analyses);codes=['KOR','DEU','CAN'];matrix=[[next(p['share_change'] for p in analyses[k]['partners'] if p['code']==c) for k in keys] for c in codes]
    fig,ax=plt.subplots(figsize=(9,3.8));cmap=LinearSegmentedColormap.from_list('shares',['#b86b4c','#faf9ed','#2d806b'])
    image=ax.imshow(matrix,cmap=cmap,norm=TwoSlopeNorm(vmin=-6,vcenter=0,vmax=6),aspect='auto')
    for i,row in enumerate(matrix):
        for j,value in enumerate(row):ax.text(j,i,f'{value:+.2f}',ha='center',va='center',color='#ffffff' if abs(value)>4 else '#274936',fontsize=13)
    ax.set_xticks(range(4),['2019→2023','2020→2023','2021→2023','2022→2023']);ax.set_yticks(range(3),[NAMES[c] for c in codes]);ax.set_title('份额变化对时间窗口的敏感性（百分点）',pad=15)
    fig.colorbar(image,ax=ax,label='百分点',shrink=.8);finish(fig,'03-窗口敏感性')

def main():
    if not READ('validation.json')['mechanical_pass']:raise SystemExit('Mechanical pilot checks must pass first')
    OUT.mkdir(parents=True,exist_ok=True);FIG.mkdir(exist_ok=True)
    analyses={k:READ(f'inputs/{k}.json') for k in ['main','window_2020','window_2021','window_2022']}
    r=analyses['main'];p={x['code']:x for x in r['partners']};summary=r['summary']
    charts(analyses)
    only_base=[x for x in r['partners'] if x['baseline'] is not None and x['current'] is None]
    only_end=[x for x in r['partners'] if x['baseline'] is None and x['current'] is not None]
    comparable=[x for x in r['partners'] if x['baseline'] is not None and x['current'] is not None]
    base_only=sum(x['baseline'] for x in only_base);end_only=sum(x['current'] for x in only_end)
    assert abs(end_only-base_only-r['structure']['change_residual'])<1e-6
    evidence_table='\n'.join(f'|{NAMES[c]}|{p[c]["baseline"]/1e8:.2f}|{p[c]["current"]/1e8:.2f}|{p[c]["share0"]:.2f}|{p[c]["share1"]:.2f}|{p[c]["share_change"]:+.2f}|{p[c]["evidence_id"]}|' for c in ORDER)
    narrative=[
        ('进口金额总体扩大，供应国表现并不同向',f'美国所选HS 8703商品名义美元进口金额由{summary["baseline"]/1e8:.2f}亿美元增至{summary["current"]/1e8:.2f}亿美元，区间增长{summary["growth"]:.2f}%。这只描述进口金额，不代表美国汽车消费总量或实际需求增长。',['main:'+summary['evidence_id']]),
        ('韩国份额改善，墨西哥更多体现市场规模分量','韩国份额由9.10%升至14.86%，提高5.76个百分点；金额增加149.18亿美元，对称分解中的供应份额分量为112.31亿美元、市场规模分量为36.87亿美元。墨西哥金额增加69.06亿美元，其市场规模分量65.52亿美元明显大于供应份额分量3.54亿美元。相似的金额增长，需要不同的描述；这些分量都不能自动解释为竞争力或政策效应。',['main:'+p['KOR']['evidence_id'],'main:'+p['MEX']['evidence_id']]),
        ('日本是“金额增长、份额下降”的清晰反例','美国自日本进口金额由399.31亿美元增至408.77亿美元，增长2.37%，但日本份额下降2.81个百分点。金额上升与相对位置下降可以同时发生，因为该市场总进口金额增长更快。',['main:'+p['JPN']['evidence_id'],'main:'+summary['evidence_id']]),
        ('长期位置与最近一年不能混为一谈','韩国在四个窗口中份额均上升；德国前三个窗口上升，但2022—2023下降约0.25个百分点；加拿大2019—2023下降约4.48个百分点，但2022—2023回升约0.92个百分点。窗口共享终点、彼此重叠，仅用于描述性敏感性检查，不能作为独立重复试验或因果稳健性证明。',['main:'+p['CAN']['evidence_id'],'window_2022:'+next(x['evidence_id'] for x in analyses['window_2022']['partners'] if x['code']=='CAN'),'window_2022:'+next(x['evidence_id'] for x in analyses['window_2022']['partners'] if x['code']=='DEU')]),
    ]
    scope='报告国：美国；流向：进口；伙伴：各来源国家或地区；商品：HS 8703（以H0定义的人员运输机动车范围为准，本文简称乘用车）；时期：2019—2023；金额：名义美元。数据包截至2023，不声称代表当前最新贸易格局。'
    limits='来源为WITS发布表、底层UN Comtrade，原单位为千美元并显示两位小数；本文换算成美元和亿美元。没有填补缺失伙伴，不自动混合镜像出口，不识别政策因果、产品质量、利润或实际消费。HHI在当前引擎中未输出。'
    residual=f'两期均有可用记录的伙伴{len(comparable)}个。仅基期有记录{len(only_base)}个，金额合计{base_only:,.0f}美元；仅报告期有记录{len(only_end)}个，金额合计{end_only:,.0f}美元。两者净差{end_only-base_only:+,.0f}美元，恰好对应变化对账残差。各期世界总额与列示伙伴合计均相差20美元；本例变化残差不能笼统归因于舍入。仅一端有记录不等于明确进入或退出。'
    notes='\n\n'.join(title+'：'+text+'（'+', '.join(refs)+'）' for title,text,refs in narrative)+'\n\n'+residual+'\n\n'+limits
    md=f'# 美国乘用车进口来源变化：主案例分析报告\n\n分析日期：2026年10月18日；工作稿，基于冻结数据，可复算。\n\n{scope}\n\n{limits}\n\n'
    for title,text,refs in narrative:md+=f'## {title}\n\n{text}\n\n证据：'+', '.join(refs)+'。\n\n'
    md+='## 主要伙伴金额与份额\n\n金额单位：亿美元；份额单位：%；份额变化单位：百分点。\n\n|伙伴|2019金额|2023金额|2019份额|2023份额|份额变化|主窗口证据|\n|---|---:|---:|---:|---:|---:|---|\n'+evidence_table+'\n\n'
    md+='## 缺失与对账\n\n'+residual+'\n\n证据：main:'+r['structure']['residual_evidence_id']+'。\n\n'
    md+='## 图表和完整证据\n\n[打开带图表和证据索引的完整HTML](主案例分析报告.html)。图表另提供PNG与SVG，可用于后续材料。\n\n'
    md+='## AI预实验的用途与边界\n\n已用当前对话宿主AI完成12题：解释分解、纠正金额/份额混用、识别缺失与因果边界、比较时间窗口。36项结构化数值与26处引用通过机械检查。问题设计、参考值阅读和回答均在同一上下文完成，未独立评分、未做普通AI对照，不能报告模型准确率或优越性。该步骤只支持进入真实模型接入试验，不代表应用内模型已接通。\n\n'
    md+='## 数据与计算指纹\n\n数据SHA256：`'+r['data_sha256']+'`。主分析ID：`'+r['analysis_id']+'`。原始页面、独立Fraction参考值、任务、首次回答和校验日志见evaluation/host-pilot-20261018。\n'
    (OUT/'主案例分析报告.md').write_text(md,encoding='utf-8')
    table='<div class="scroll"><table><tr><th>伙伴</th><th>2019金额 / 亿美元</th><th>2023金额 / 亿美元</th><th>2019份额 / %</th><th>2023份额 / %</th><th>份额变化 / pp</th></tr>'+''.join(f'<tr><td>{NAMES[c]}</td><td>{p[c]["baseline"]/1e8:.2f}</td><td>{p[c]["current"]/1e8:.2f}</td><td>{p[c]["share0"]:.2f}</td><td>{p[c]["share1"]:.2f}</td><td>{p[c]["share_change"]:+.2f}</td></tr>' for c in ORDER)+'</table></div>'
    sections=''
    for i,(title,text,refs) in enumerate(narrative):
        sections+=f'<h2>{i+1}. {E(title)}</h2><p>{E(text)}</p><p class="refs">'+ref_html(refs)+'</p>'
        if i==0:sections+='<figure><img src="figures/01-金额与份额.png" alt="进口金额和主要伙伴份额"><figcaption>图1：金额扩张与来源份额变化分别观察，非实际消费指标。</figcaption></figure>'
        if i==1:sections+='<figure><img src="figures/02-对称分解.png" alt="市场规模与份额分解"><figcaption>图2：绿色为市场规模分量，棕色为供应份额分量；深色菱形为两项相加后的净变化。分量不代表因果效应。</figcaption></figure>'
        if i==3:sections+='<figure><img src="figures/03-窗口敏感性.png" alt="时间窗口敏感性"><figcaption>图3：所有窗口均以2023为终点，非独立样本。</figcaption></figure>'
    evidence=''
    for key,a in analyses.items():
        for ev in a['evidence']:
            evidence+=f'<details id="{key}-{ev["id"]}"><summary>{key}:{ev["id"]} · {E(ev["label"])}</summary><p>{E(ev["formula"])}</p><pre>{E(json.dumps({k:ev[k] for k in ["operands","result","unit","status","records"]},ensure_ascii=False,indent=2))}</pre></details>'
    source_list=''.join(f'<li><a href="{E(s["url"],quote=True)}">{E(s["id"])}</a><br><small>SHA256 {E(s["sha256"])}</small></li>' for s in r['sources'] if s['id'].startswith('USA-') and '-Imports-8703' in s['id'])
    body=f'<span class="tag">真实案例工作稿</span><span class="tag">2026-10-18</span><h1>市场扩大，供应国表现为何不同？<br>美国乘用车进口来源变化</h1><p class="muted">{E(scope)}</p><div class="note warning">{E(limits)}</div>{sections}<h2>主要伙伴数据</h2>{table}<h2>缺失与对账</h2><p>{E(residual)}</p><h2>AI预实验</h2><p>当前对话宿主AI完成12道开发题，36项结构化数值与26处引用通过机械检查。非盲测、无普通AI基线、无独立语义评分，不能报告准确率或优越性。</p><p><a href="AI预实验报告.html">查看每道题、宿主AI回答和校验边界</a></p><h2>数据与来源</h2><p class="refs">数据SHA256：{r["data_sha256"]}<br>主分析ID：{r["analysis_id"]}</p><ul class="refs">{source_list}</ul><h2>完整证据索引</h2><p>引用带窗口前缀，避免不同分析重复使用相同E编号时混淆。</p>{evidence}'
    (OUT/'主案例分析报告.html').write_text(page('美国乘用车主案例',body),encoding='utf-8')
    tasks={t['id']:t for t in READ('tasks.json')};responses=READ('answers.first.json')['responses'];check=READ('validation.json');protocol=READ('protocol.json')
    pilot_md='# 宿主AI开发预实验报告\n\n**非盲测、非独立上下文、没有普通AI基线；不能称为模型准确率测试。**\n\n'
    pilot_md+=f'完成{len(responses)}道题，机械检查{check["numeric_claims_checked"]}项结构化数值、{check["citation_occurrences_checked"]}处引用，未发现不一致。检查不自动覆盖正文语义。\n\n'
    pilot_body='<span class="tag">宿主AI开发预实验</span><h1>解释、核查与识别证据不足：12道开发题</h1><div class="note warning">同一助手设计问题、阅读参考值并作答；没有独立基线或评分。以下机械校验不代表模型准确率。应用内模型仍未连接。</div><p>证据和任务先冻结，宿主AI随后直接撰写首次回答；脚本不生成回答。36项结构化数值和26处引用通过校验，引用存在不等于语义一定支持。</p>'
    for response in responses:
        task=tasks[response['id']];title=response['id']+' · '+task['category']
        pilot_md+=f'## {title}\n\n问题：{task["question"]}\n\n宿主AI回答：{response["answer"]}\n\n引用：'+', '.join(response['citations'])+'\n\n状态：机械校验通过；语义仅同一助手自审。\n\n'
        pilot_body+=f'<h2>{E(title)}</h2><h3>问题</h3><p>{E(task["question"])}</p><h3>宿主AI首次回答</h3><p class="response">{E(response["answer"])}</p><p class="refs">{ref_html(response["citations"])}</p><p class="check">结构化数值及引用机械校验通过；语义未独立评分。</p>'
    conclusion='本预实验展示了可追溯解释的可行性：金额与份额区分、分解解释和拒绝过度推断都能形成可核查回答。但没有证明这些能力是本系统独有，也没有证明比普通AI更准、更快。下一阶段先修复证据选择与跨窗口工具，再接通真实模型，在信息和工具条件公平的对照中测试，并保留首次失败与重试。'
    pilot_md+='## 可以得出的结论\n\n'+conclusion+'\n\n## 限制\n\n'+'\n'.join('- '+x for x in protocol['limitations'])+'\n'
    pilot_body+='<h2>可以得出的结论</h2><p>'+E(conclusion)+'</p><h2>限制</h2><ul>'+''.join('<li>'+E(x)+'</li>' for x in protocol['limitations'])+'</ul><p class="refs">首次回答SHA256：'+check['answers_sha256']+'</p>'
    gap='静态检查发现：当前应用AI证据包仅保留金额变化绝对值最大的八个伙伴，本例不含日本和直布罗陀；且仅支持当前单一时间窗口。P03、P06、P09、P12所需参考引用不能全部进入该固定包。宿主AI本轮读取了完整结果与四个窗口，信息条件明显不同；本次回答还使用结构化数值清单，而非应用API的claimsJSON及禁止自由数字协议。因此，本预实验不是当前应用AI接口的端到端验证。'
    next_steps='建议新增指定伙伴证据查询（国家代码须从目录校验）、受限年份窗口比较（由分析引擎执行、不能让模型自行编程）、带分析ID的证据命名空间，以及模型输出数值字段与引用的绑定校验。保留P03/P06/P09/P12作为开发回归题；正式对照另建未参与调试的题集。'
    pilot_md+='\n## 当前应用接口差异\n\n'+gap+'\n\n'+next_steps+'\n'
    pilot_body+='<h2>当前应用接口差异</h2><div class="note warning">'+E(gap)+'</div><p>'+E(next_steps)+'</p>'
    (OUT/'AI预实验报告.md').write_text(pilot_md,encoding='utf-8');(OUT/'AI预实验报告.html').write_text(page('宿主AI预实验',pilot_body),encoding='utf-8')
    (OUT/'应用保存笔记.txt').write_text(notes,encoding='utf-8')
    (ROOT/'docs/主案例分析报告.md').write_text(md.replace('(主案例分析报告.html)','(../研究成果/美国乘用车主案例/主案例分析报告.html)'),encoding='utf-8')
    dump={'built_at':datetime.now(timezone.utc).isoformat(),'main_analysis_id':r['analysis_id'],'data_sha256':r['data_sha256'],'pilot_answers_sha256':check['answers_sha256'],
        'artifacts':{str(f.relative_to(OUT)).replace('\\','/'):hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(OUT.rglob('*')) if f.is_file() and f.name!='artifacts.json'}}
    (OUT/'artifacts.json').write_text(json.dumps(dump,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'out':str(OUT),'figures':6,'responses':len(responses),'artifacts':len(dump['artifacts'])},ensure_ascii=False))

if __name__=='__main__':main()

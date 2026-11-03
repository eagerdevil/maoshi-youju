"""Freeze a transparent, unblinded host-conversation pilot. Does not invoke a model.

References are independently computed with Fraction from retained CSV values.
No raw data, previous evaluation or application code is modified.
"""
from __future__ import annotations
import hashlib, json, shutil, sys
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'.vendor'));sys.path.insert(0,str(ROOT))
from backend.analysis import Spec,analyse
from backend.data import get_dataset

OUT=ROOT/'evaluation/host-pilot-20261018'

def dump(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')

def prepare():
    if (OUT/'freeze.json').exists():raise SystemExit('Pilot already frozen; do not overwrite. Use another run directory for a new protocol.')
    OUT.mkdir(parents=True,exist_ok=True)
    rows,manifest,sha=get_dataset('wits-core')
    result=analyse(Spec(products=['8703']),(rows,manifest,sha))
    analyses={'main':result}
    for year in [2020,2021,2022]:
        analyses[f'window_{year}']=analyse(Spec(products=['8703'],base_year=year),(rows,manifest,sha))
    for key,r in analyses.items():dump(OUT/f'inputs/{key}.json',r)
    def value(year,partner):
        matched=[r for r in rows if (r['reporter'],r['partner'],r['year'],r['flow'],r['product'])==('USA',partner,year,'M','8703')]
        if len(matched)!=1 or matched[0]['value'] is None:raise ValueError('Missing or nonunique reference observation')
        return Fraction(matched[0]['value'])
    independent={}
    for key,r in analyses.items():
        year=r['spec']['base_year'];m0=value(year,'WLD');m1=value(2023,'WLD')
        partners={}
        for p in r['partners']:
            if p['baseline'] is None or p['current'] is None:continue
            x0=value(year,p['code']);x1=value(2023,p['code']);s0=x0/m0;s1=x1/m1
            scale=(s0+s1)/2*(m1-m0);share=(m0+m1)/2*(s1-s0)
            assert scale+share==x1-x0
            partners[p['code']]={'baseline':float(x0),'current':float(x1),'delta':float(x1-x0),
                'share0':float(s0*100),'share1':float(s1*100),'share_change':float((s1-s0)*100),
                'growth':float((x1/x0-1)*100) if x0 else None,
                'market_component':float(scale),'share_component':float(share),
                'contribution_pp':float((x1-x0)/m0*100),
                'exact_fraction':{'delta':str(x1-x0),'market_component':str(scale),'share_component':str(share)}}
            for metric in ['baseline','current','delta','share0','share1','share_change','growth','market_component','share_component','contribution_pp']:
                expected=partners[p['code']][metric];actual=p.get(metric)
                if expected is None:assert actual is None
                else:assert abs(actual-expected)<=max(1e-7,abs(expected)*1e-12),(key,p['code'],metric)
        total={'baseline':float(m0),'current':float(m1),'delta':float(m1-m0),'growth':float((m1/m0-1)*100)}
        for field,expected in total.items():assert abs(r['summary'][field]-expected)<1e-6
        independent[key]={'summary':total,'partners':partners,
            'largest_absolute_delta_partner':max(partners,key=lambda c:abs(partners[c]['delta']))}
    dump(OUT/'reference.json',independent)
    def citation(code,key='main'):
        p=next(p for p in analyses[key]['partners'] if p['code']==code)
        return f'{key}:{p["evidence_id"]}'
    tasks=[
        ('P01','数值查询','说明这份分析的报告国、流向、商品、时期、总进口金额和区间增长率。',
         [f'main:{result["summary"]["evidence_id"]}'],['不得把名义进口金额增长写成实际汽车消费需求增长。']),
        ('P02','贡献解释','哪个两期可比伙伴的金额变化绝对值最大？解释其两个分解分量，并说明分量不是因果效应。',
         [citation('KOR')],['按绝对金额变化比较全部可比伙伴。','不能把供应份额分量命名为已识别的竞争力或政策效应。']),
        ('P03','核查判断','核查这句话：“日本的份额下滑，所以美国自日本进口的乘用车金额也下降了。”给出建议改写。',
         [citation('JPN')],['金额上升而份额下降。','使用美国报告的进口表述，不偷换成日本报告的出口。']),
        ('P04','单位核查','核查这句话：“韩国在美国该进口市场的份额提高了5.76%。”百分点与百分比是否混用？',
         [citation('KOR')],['应为约5.76个百分点。']),
        ('P05','分解解释','墨西哥对美供应金额增长，能否直接说明增长主要来自竞争力提高？比较两个分量。',
         [citation('MEX')],['市场规模分量明显较大。','描述性分解不识别竞争力原因。']),
        ('P06','时间窗口','加拿大2019—2023份额下降，是否能写成每年都在下降？请比较2022—2023窗口。',
         [citation('CAN'),citation('CAN','window_2022')],['长窗口下降，短窗口回升，不是单调下降证据。']),
        ('P07','因果边界','这些数据是否足以证明某项关税政策导致韩国份额上升？如果不足，需要补充什么研究证据？',
         [citation('KOR')],['不得虚构特定政策事实。','需要明确政策时点、暴露程度、对照与识别策略。']),
        ('P08','对象边界','能否写成：“美国汽车消费市场2019—2023实际增长17.14%”？指出对象和价格口径问题。',
         [f'main:{result["summary"]["evidence_id"]}'],['进口金额不等于国内汽车消费市场总量。','名义美元不等于实际增长。']),
        ('P09','缺失处理','直布罗陀2019年有记录、2023年无记录，是否可以认定其退出市场并计算为负百分之百？',
         [citation('GIB')],['缺失不等于明确零。','状态未知，不能计算退出或负百分之百。']),
        ('P10','角色消歧','不沿用当前筛选：请比较中美汽车贸易。请先说明应澄清什么，再决定查询方式。',
         [],['澄清双边方向、各国对世界或第三方目标市场。','澄清商品边界、时期、报告方；不自动选择一种。']),
        ('P11','结构边界','前五列示伙伴份额略降，能否证明进口供应风险显著降低并给出精确HHI？',
         [f'main:{result["structure"]["baseline"]["evidence_id"]}',f'main:{result["structure"]["current"]["evidence_id"]}'],
         ['微小份额变化不等于风险显著降低。','当前引擎HHI为空，不编造指数。']),
        ('P12','稳健性探索','分别使用2019、2020、2021、2022为基期比较2023，韩国、德国、加拿大的份额方向是否一致？',
         [citation(c,key) for key in analyses for c in ['KOR','DEU','CAN']],
         ['韩国所有窗口上升。','德国最后窗口下降，加拿大最后窗口上升。','窗口重叠且非因果稳健性检验。']),
    ]
    dump(OUT/'tasks.json',[{'id':tid,'category':category,'question':q,'reference_citations':refs,'criteria':criteria} for tid,category,q,refs,criteria in tasks])
    protocol={'study_type':'unblinded_host_conversation_development_pilot','created_at':datetime.now(timezone.utc).isoformat(),
        'task_count':len(tasks),'data_sha256':sha,'main_analysis_id':result['analysis_id'],
        'model_provenance':'当前对话宿主AI；具体部署模型ID未获取；未调用应用API或另启独立模型。',
        'procedure':['冻结任务、参考值、证据及源文件指纹。','宿主AI阅读当前对话工具结果后直接撰写回答。','计算程序仅检查引用和结构化数值，不生成或代答AI文本。'],
        'limitations':['同一助手参与任务设计、阅读参考值并作答，非盲测。','没有独立普通AI基线或独立评分者，不推导优越性或总体准确率。','不记录不可核实的模型用时、成本或额度。','回答成功不代表应用内模型已接通。','预实验题只用于开发，后续不得继续称为未见保留题。']}
    dump(OUT/'protocol.json',protocol)
    for source in result['sources']:
        if source['id'].startswith('USA-') and '-Imports-8703' in source['id']:
            src=ROOT/source['raw_file'];dst=OUT/'sources'/src.name;dst.parent.mkdir(exist_ok=True);shutil.copyfile(src,dst)
    for src in [ROOT/'data/processed/wits-core.csv',ROOT/'data/processed/wits-core.manifest.json',ROOT/'backend/analysis.py',ROOT/'backend/data.py']:
        dst=OUT/'frozen'/src.name;dst.parent.mkdir(exist_ok=True);shutil.copyfile(src,dst)
    fingerprint={str(p.relative_to(OUT)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(OUT.rglob('*')) if p.is_file()}
    dump(OUT/'freeze.json',{'created_at':datetime.now(timezone.utc).isoformat(),'files':fingerprint})
    print(json.dumps({'out':str(OUT),'tasks':len(tasks),'frozen_files':len(fingerprint),'main_analysis_id':result['analysis_id'],'evidence_map':{t[0]:t[3] for t in tasks}},ensure_ascii=False,indent=2))

if __name__=='__main__':prepare()

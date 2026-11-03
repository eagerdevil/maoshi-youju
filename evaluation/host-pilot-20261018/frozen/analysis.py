from __future__ import annotations
import hashlib, json
from decimal import Decimal, localcontext
from pydantic import BaseModel, Field, ConfigDict, model_validator
from typing import Literal
from .data import get_dataset, DataError

VERSION='0.1.0'
COUNTRIES={'USA':'美国','CHN':'中国','DEU':'德国','JPN':'日本','GBR':'英国','WLD':'世界'}

class Spec(BaseModel):
    model_config=ConfigDict(extra='forbid')
    dataset_id: str='wits-core'
    mode: Literal['competition','bilateral','comparison']='competition'
    reporter: str='USA'
    reporters: list[str]=Field(default_factory=lambda:['CHN','DEU','JPN'],min_length=1,max_length=6)
    partner: str='CHN'
    flow: Literal['M','X']='M'
    products: list[str]=Field(default_factory=lambda:['0902'],min_length=1,max_length=12)
    base_year: int=2019
    end_year: int=2023

    @model_validator(mode='after')
    def check(self):
        if not 1960<=self.base_year<self.end_year<=2100: raise ValueError('报告期必须晚于基期')
        if len(set(self.products))!=len(self.products): raise ValueError('商品重复')
        if len(set(self.reporters))!=len(self.reporters): raise ValueError('报告国重复')
        if any(a!=b and b.startswith(a) for a in self.products for b in self.products):
            raise ValueError('商品父子层级重叠，禁止重复汇总')
        if self.mode=='bilateral' and (self.partner=='WLD' or self.partner==self.reporter):
            raise ValueError('双边模式须选择不同的两个国家或地区')
        if self.mode=='competition' and self.flow!='M': raise ValueError('目标市场模式使用目标国报告的进口')
        return self

def n(value):
    return None if value is None else float(value)

def growth(a,b):
    return (b/a-1)*100 if a is not None and b is not None and a>0 else None

def analyse(spec: Spec, injected=None):
    with localcontext() as context:
        context.prec=40
        return _analyse(spec,injected)

def _analyse(spec, injected):
    rows,manifest,fingerprint = injected if injected else get_dataset(spec.dataset_id)
    selected_reporters=spec.reporters if spec.mode=='comparison' else [spec.reporter]
    flow='M' if spec.mode=='competition' else spec.flow
    selected=[r for r in rows if r['reporter'] in selected_reporters and r['flow']==flow and r['product'] in spec.products and spec.base_year<=r['year']<=spec.end_year]
    if not selected: raise DataError('此国家、行业、流向与年份组合没有数据，请查看覆盖矩阵')
    classes={r['classification'] for r in selected}
    if len(classes)!=1: raise DataError('所选数据跨商品分类版本，须先进行有依据的分类衔接')
    index={(r['reporter'],r['partner'],r['year'],r['product']):r for r in selected}
    if len(index)!=len(selected): raise DataError('数据存在重复主键，分析停止')
    if any(r.get('partner_type')=='aggregate' for r in selected): raise DataError('数据含区域汇总，与成员混用可能重复；本版须先单独筛选非汇总记录')
    names={r['partner']:r['partner_name'] for r in selected}|{r['reporter']:r['reporter_name'] for r in selected}
    names.update({k:v for k,v in COUNTRIES.items() if k in names})
    product_names={r['product']:r['product_name'] for r in selected}
    evidence=[]
    def obs(reporter,partner,year,products=None):
        rr=[index.get((reporter,partner,year,p)) for p in (products or spec.products)]
        complete=all(r is not None and r['value'] is not None for r in rr)
        return (sum((r['value'] for r in rr),Decimal(0)) if complete else None,[r for r in rr if r is not None])
    def ev(label,formula,operands,result,rr,unit='USD'):
        eid=f'E{len(evidence)+1:04d}'
        unique={r['record_id']:r for r in rr}
        evidence.append({'id':eid,'label':label,'formula':formula,'operands':{k:str(v) if v is not None else None for k,v in operands.items()},
            'result':str(result) if result is not None else None,'unit':unit,'status':'supported' if result is not None else 'insufficient',
            'record_ids':list(unique),'records':[{k:v for k,v in r.items() if k!='value'} for r in unique.values()],
            'note':'缺失记录不按零计算。金额为公开表舍入值；名义美元变化不等于实际增长。'})
        return eid
    def pair(reporter,partner,products=None):
        a,ar=obs(reporter,partner,spec.base_year,products); b,br=obs(reporter,partner,spec.end_year,products)
        return a,b,ar+br
    coverage=[]
    for reporter in selected_reporters:
        coverage.append({'reporter':reporter,'name':names.get(reporter,reporter),'years':[
            {'year':y,'available':obs(reporter,'WLD',y)[0] is not None} for y in range(spec.base_year,spec.end_year+1)]})
    warnings=list(manifest.get('limitations',[]))
    warnings.append('份额变化和贡献分解属于描述性分析，不能识别政策因果效应或证明竞争力增强。')
    comparisons=[]; partners=[]; structure=None
    if spec.mode=='comparison':
        for reporter in selected_reporters:
            a,b,rr=pair(reporter,'WLD'); d=b-a if a is not None and b is not None else None
            eid=ev(f"{names.get(reporter,reporter)}总额变化",'ΔV = V₁−V₀；区间增长率 = (V₁/V₀−1) × 100%（V₀>0）',{'base':a,'end':b,'growth_percent':growth(a,b)},d,rr)
            comparisons.append({'code':reporter,'name':names.get(reporter,reporter),'baseline':n(a),'current':n(b),'delta':n(d),'growth':n(growth(a,b)),'evidence_id':eid})
        a=b=None; summary_rr=[]
        title='多国贸易表现比较'
    else:
        main_partner=spec.partner if spec.mode=='bilateral' else 'WLD'
        a,b,summary_rr=pair(spec.reporter,main_partner)
        title=f"{names.get(spec.reporter,spec.reporter)}{(' ← '+names.get(spec.partner,spec.partner)) if spec.mode=='bilateral' and flow=='M' else (' → '+names.get(spec.partner,spec.partner)) if spec.mode=='bilateral' else '进口市场'}"
        if spec.mode=='bilateral':
            for p in spec.products:
                pa,pb,rr=pair(spec.reporter,spec.partner,[p]); d=pb-pa if pa is not None and pb is not None else None
                eid=ev(f'{product_names[p]}双边金额变化','ΔV = V₁−V₀；区间增长率 = (V₁/V₀−1) × 100%（V₀>0）',{'base':pa,'end':pb,'growth_percent':growth(pa,pb)},d,rr)
                partners.append({'code':p,'name':product_names[p],'baseline':n(pa),'current':n(pb),'delta':n(d),'growth':n(growth(pa,pb)),
                    'share0':n(pa/a*100) if pa is not None and a else None,'share1':n(pb/b*100) if pb is not None and b else None,
                    'contribution_pp':n(d/a*100) if d is not None and a else None,'evidence_id':eid,'status':'comparable' if d is not None else 'unknown'})
        else:
            codes=sorted({r['partner'] for r in selected if r['partner']!='WLD' and r.get('partner_type','country_or_area')=='country_or_area'})
            for code in codes:
                pa,pb,rr=pair(spec.reporter,code); d=pb-pa if pa is not None and pb is not None else None
                s0=pa/a if pa is not None and a else None; s1=pb/b if pb is not None and b else None
                market=(s0+s1)/2*(b-a) if s0 is not None and s1 is not None else None
                share=(a+b)/2*(s1-s0) if s0 is not None and s1 is not None else None
                status='unknown' if pa is None or pb is None else 'entry' if pa==0 and pb>0 else 'exit' if pa>0 and pb==0 else 'continuing'
                eid=ev(f'{names.get(code,code)}供应变化分解','Δx = (s₀+s₁)/2 × (M₁−M₀) + (M₀+M₁)/2 × (s₁−s₀)',
                    {'M0':a,'M1':b,'x0':pa,'x1':pb,'s0':s0,'s1':s1,'market_component':market,'share_component':share,
                        'growth_percent':growth(pa,pb),'share_change_pp':(s1-s0)*100 if s0 is not None and s1 is not None else None,
                        'contribution_pp':d/a*100 if d is not None and a else None},d,rr+summary_rr)
                partners.append({'code':code,'name':names.get(code,code),'baseline':n(pa),'current':n(pb),'delta':n(d),'growth':n(growth(pa,pb)),
                    'share0':n(s0*100) if s0 is not None else None,'share1':n(s1*100) if s1 is not None else None,
                    'share_change':n((s1-s0)*100) if s0 is not None and s1 is not None else None,
                    'contribution_pp':n(d/a*100) if d is not None and a else None,'market_component':n(market),'share_component':n(share),
                    'status':status,'evidence_id':eid})
            def concentration(year,total):
                amounts=[obs(spec.reporter,c,year)[0] for c in codes]
                values=sorted([x for x in amounts if x is not None],reverse=True)
                reported=sum(values,Decimal(0)); residual=total-reported if total is not None else None
                eid=ev(f'{year}年伙伴覆盖与统计残差','世界总额－已列示伙伴合计',{'world':total,'listed_sum':reported},residual,
                    [r for r in selected if r['year']==year])
                # Full concentration is not identifiable from a public rounded table with absent/special partners.
                return {'year':year,'world':n(total),'listed_sum':n(reported),'residual':n(residual),
                    'coverage_pct':n(reported/total*100) if total else None,
                    'listed_top3_share':n(sum(values[:3],Decimal(0))/total*100) if total else None,
                    'listed_top5_share':n(sum(values[:5],Decimal(0))/total*100) if total else None,
                    'hhi':None,'hhi_reason':'公开表含舍入、未列示或特殊伙伴，暂不声明完整市场构成；不输出整体HHI。','evidence_id':eid}
            structure={'baseline':concentration(spec.base_year,a),'current':concentration(spec.end_year,b)}
            comparable_delta=Decimal(0)
            for code in codes:
                ca,cb,_=pair(spec.reporter,code)
                if ca is not None and cb is not None: comparable_delta+=cb-ca
            residual=(b-a)-comparable_delta if a is not None and b is not None else None
            structure['change_residual']=n(residual)
            structure['residual_evidence_id']=ev('变化贡献对账残差','总额变化－两期可比伙伴的金额变化合计',{'total_delta':b-a if a is not None and b is not None else None,'comparable_delta':comparable_delta},residual,selected)
    delta=b-a if a is not None and b is not None else None
    summary_eid=ev('总体金额变化','ΔV = V₁−V₀；区间增长率 = (V₁/V₀−1) × 100%（V₀>0）',{'base':a,'end':b,'growth_percent':growth(a,b)},delta,summary_rr) if spec.mode!='comparison' else None
    summary={'baseline':n(a),'current':n(b),'delta':n(delta),'growth':n(growth(a,b)),'evidence_id':summary_eid}
    series=[]
    for y in range(spec.base_year,spec.end_year+1):
        values={}; evidence_ids={}
        for reporter in selected_reporters:
            partner=spec.partner if spec.mode=='bilateral' else 'WLD'
            value,rr=obs(reporter,partner,y)
            values[reporter]=n(value)
            evidence_ids[reporter]=ev(f'{names.get(reporter,reporter)} {y}年金额','所选商品金额合计',{'value':value},value,rr)
        series.append({'year':y,'values':values,'evidence_ids':evidence_ids})
    partners.sort(key=lambda p:p['current'] if p['current'] is not None else -1,reverse=True)
    insights=[]
    if delta is not None:
        insights.append({'text':f'所选范围金额由{float(a):,.0f}美元变为{float(b):,.0f}美元，变化{float(delta):+,.0f}美元。','evidence_ids':[summary_eid]})
    if spec.mode=='competition':
        comparable=[p for p in partners if p['delta'] is not None]
        if comparable:
            top=max(comparable,key=lambda p:abs(p['delta']))
            insights.append({'text':f"在两期可比伙伴中，{top['name']}的金额变动绝对值最大；这不是对其变化原因的因果判断。",'evidence_ids':[top['evidence_id']]})
    if any(not y['available'] for c in coverage for y in c['years']): warnings.append('部分国家或年份缺少世界分母，缺值保留为空；不得按零比较。')
    if spec.mode=='comparison': warnings.append('各国使用各自报告数据；金额规模、增长率与基期指数应分别理解，不汇总为全球总额。')
    payload=spec.model_dump(); aid=hashlib.sha256(json.dumps({'spec':payload,'data':fingerprint,'version':VERSION},sort_keys=True).encode()).hexdigest()[:20]
    return {'analysis_id':aid,'version':VERSION,'spec':payload,'title':title,'flow':flow,'classification':next(iter(classes)),
        'product_label':'、'.join(product_names[p] for p in spec.products),'names':names,'summary':summary,'series':series,
        'partners':partners,'comparisons':comparisons,'structure':structure,'coverage':coverage,'insights':insights,
        'warnings':list(dict.fromkeys(warnings)),'evidence':evidence,'data_sha256':fingerprint,
        'sources':manifest.get('sources',[]),'dataset_name':manifest['name']}

"""Mechanical audit of frozen inputs, citations and declared numbers; no semantic score."""
from __future__ import annotations
import csv, hashlib, json, sys
from datetime import datetime,timezone
from fractions import Fraction
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'evaluation/host-pilot-20261018'

def read(name):return json.loads((OUT/name).read_text(encoding='utf-8'))

def validate():
    freeze=read('freeze.json');failures=[]
    for name,digest in freeze['files'].items():
        if hashlib.sha256((OUT/name).read_bytes()).hexdigest()!=digest:failures.append('Frozen file changed: '+name)
    analyses={key:read(f'inputs/{key}.json') for key in ['main','window_2020','window_2021','window_2022']}
    reference=read('reference.json');tasks=read('tasks.json');answers=read('answers.first.json')['responses']
    rows=list(csv.DictReader((OUT/'frozen/wits-core.csv').open(encoding='utf-8-sig')))
    rows=[r for r in rows if r['reporter']=='USA' and r['flow']=='M' and r['product']=='8703']
    def value(year,partner):
        rr=[r for r in rows if int(r['year'])==year and r['partner']==partner]
        if not rr:return None
        assert len(rr)==1
        return Fraction(rr[0]['value_usd']) if rr[0]['value_usd'] else None
    def ground(claim):
        key=claim['analysis'];metric=claim['metric'];r=analyses[key]
        if claim['scope']=='summary':return reference[key]['summary'][metric]
        if claim['scope']=='partner':
            code=claim['partner']
            if code in reference[key]['partners']:return reference[key]['partners'][code][metric]
            a=value(r['spec']['base_year'],code);b=value(2023,code)
            if (a is None or b is None) and metric in {'delta','growth','share_change','market_component','share_component','contribution_pp'}:return None
            raise ValueError('Unexpected incomplete metric')
        if claim['scope']=='structure':
            year=r['spec']['base_year'] if claim['period']=='baseline' else 2023
            vals=[Fraction(x['value_usd']) for x in rows if int(x['year'])==year and x.get('partner_type')=='country_or_area' and x['value_usd']]
            total=value(year,'WLD')
            if metric=='listed_top5_share':return float(sum(sorted(vals,reverse=True)[:5],Fraction(0))/total*100)
        raise ValueError('Unknown metric request')
    taskmap={t['id']:t for t in tasks};seen=set();numeric=0;citations=0;details=[]
    for answer in answers:
        key=answer['id'];issues=[]
        if key not in taskmap or key in seen:issues.append('Unknown or duplicate task')
        seen.add(key)
        refs=answer.get('citations',[])
        for ref in refs:
            analysis,eid=ref.split(':',1)
            if analysis not in analyses or not any(e['id']==eid for e in analyses[analysis]['evidence']):issues.append('Unknown citation: '+ref)
            citations+=1
        if key in taskmap and not set(taskmap[key]['reference_citations']).issubset(set(refs)):
            issues.append('Missing required reference citation')
        for claim in answer.get('numeric_claims',[]):
            expected=ground(claim);actual=claim['value'];unit=claim['unit'];metric=claim['metric'];numeric+=1
            money_metric=metric in {'baseline','current','delta','market_component','share_component'}
            valid_units={'USD','亿美元'} if money_metric else {'百分点'} if metric in {'share_change','contribution_pp'} else {'%'}
            if unit not in valid_units:issues.append(f'Wrong unit: {metric}/{unit}');continue
            if expected is not None and unit=='亿美元':expected/=1e8
            if expected is None:
                if actual is not None:issues.append('Missing value imputed')
            elif actual is None or abs(actual-expected)>0.5*10**(-claim['decimals'])+1e-9:
                issues.append(f'Number mismatch: {claim} vs {expected}')
        if issues:failures.extend([key+': '+issue for issue in issues])
        details.append({'id':key,'mechanical_status':'pass' if not issues else 'fail','issues':issues,'semantic_status':'not_independently_scored'})
    if seen!=set(taskmap):failures.append('Tasks missing from first responses')
    raw=(OUT/'answers.first.json').read_bytes();answer_sha=hashlib.sha256(raw).hexdigest()
    report={'checked_at':datetime.now(timezone.utc).isoformat(),'frozen_files_verified':len(freeze['files']),
        'responses':len(answers),'numeric_claims_checked':numeric,'citation_occurrences_checked':citations,
        'answers_sha256':answer_sha,'mechanical_pass':not failures,'failures':failures,'details':details,
        'limitations':['数值校验检查结构化数值清单，不自动证明正文中没有遗漏或过度解释。','引用存在不等于引用语义支持；语义仅同一宿主AI自审，未独立评分。','不能把完成题数或机械校验率称为模型准确率或对照优势。']}
    directory=OUT/'checks';directory.mkdir(exist_ok=True)
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    text=json.dumps(report,ensure_ascii=False,indent=2)
    (directory/f'{stamp}.json').write_text(text,encoding='utf-8');(OUT/'validation.json').write_text(text,encoding='utf-8')
    print(json.dumps({k:report[k] for k in ['responses','numeric_claims_checked','citation_occurrences_checked','mechanical_pass','failures']},ensure_ascii=False))
    return not failures

if __name__=='__main__':sys.exit(0 if validate() else 1)

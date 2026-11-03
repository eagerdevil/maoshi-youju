"""Freeze the 13 previously problematic outputs for a 0.5.3 targeted retest."""
import hashlib
import json
from pathlib import Path
import random

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'evaluation/deepseek-20261019-remaining-v3'
OUT=ROOT/'evaluation/deepseek-20261019-targeted-v4'


def read(path):return json.loads(path.read_text(encoding='utf-8'))


def main():
    if OUT.exists():raise RuntimeError('Targeted retest already prepared; do not overwrite')
    seal=read(SOURCE/'first-results-seal.json')
    for name,digest in seal['files'].items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=digest:raise RuntimeError('Original first outputs changed')
    pointer=read(SOURCE/'latest-run.json');run=ROOT/Path(pointer['summary']).parent
    tasks={t['id']:t for t in read(SOURCE/'tasks.json')};refs=read(SOURCE/'reference.json')
    selection=[(key,'pipeline','scope_rules') for key in tasks if key.endswith('-role')]
    selection += [('de-cn-tea-'+suffix,'pipeline','bilateral_pipeline') for suffix in ['numeric','injection','causal','windows']]
    selection += [('ca-cocoa-numeric','fixed_evidence','numeric_fields'),('de-cn-tea-windows','fixed_evidence','numeric_fields'),
                  ('export-coffee-windows','fixed_evidence','multi_country_windows')]
    if len(selection)!=13:raise RuntimeError('Expected exactly 13 targeted outputs')
    cases=[]
    for key,group,category in selection:
        path=run/(key+'--'+group+'.first.json')
        cases.append({'case_id':key+'--'+group,'task':tasks[key],'group':group,'category':category,
                      'source_first_result':path.relative_to(ROOT).as_posix(),'source_sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    random.Random(2026101904).shuffle(cases)
    protocol={'title':'0.5.3四类修复针对性真实复测','cases':13,'scope_rule_cases':6,'maximum_api_requests':11,
        'budget_limit_usd':0.50,'automatic_retries':0,'app_version':'0.5.3',
        'authorization':'用户要求再进行针对性复测；只运行这13份已知问题结果，不扩大到全题集，不自动重试。',
        'design':'沿用原问题、参数和固定证据计划；6条角色说明通过真实业务入口验证规则且不调用模型，4条双边流程最多各两次，3条固定证据解释各一次。',
        'scoring':'协议状态、独立Fraction参考要求数值、服务端覆盖分别统计；规则回答单独标注，不算作DeepSeek成功回答。语义评价与独立人工评价保持待完成。',
        'claim_limits':'全部是已见问题，部分流程增加确定性规则，不能称为盲评、模型准确率或同一流程的无偏对照。即使机械检查通过，正文仍需核查。',
        'price_note':'使用原2026-10-19留存Flash价保守估算，不计缓存优惠，不是账单金额保证。'}
    OUT.mkdir(parents=True)
    for name,obj in [('cases.json',cases),('reference.json',{key:refs[key] for key in sorted({c['task']['id'] for c in cases})}),('protocol.json',protocol)]:
        (OUT/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
    paths=[OUT/name for name in ['cases.json','reference.json','protocol.json']]
    paths += [ROOT/name for name in ['scripts/prepare_targeted_retest.py','scripts/run_targeted_retest.py','scripts/run_model_evaluation.py',
        'backend/services.py','backend/evidence_tools.py','backend/answer_contract.py','backend/model_runtime.py','backend/analysis.py','backend/data.py','backend/__init__.py',
        'data/processed/wits-core.csv','data/processed/wits-canada-cocoa.csv']]
    hashes={}
    for path in paths:
        name=path.relative_to(ROOT).as_posix();raw=path.read_bytes();hashes[name]=hashlib.sha256(raw).hexdigest()
        copy=OUT/'frozen'/name;copy.parent.mkdir(parents=True,exist_ok=True);copy.write_bytes(raw)
    (OUT/'freeze.json').write_text(json.dumps({'files':hashes,'note':'首次调用前冻结；不覆盖旧首次回答，运行期间不改变代码、提示和题目。'},ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'cases':13,'rule_cases_without_model':6,'maximum_api_requests':11,'live_requests':0},ensure_ascii=False))


if __name__=='__main__':main()

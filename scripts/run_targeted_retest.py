"""One real 13-case targeted retest, no automatic repeats or prompt changes."""
import argparse
import asyncio
from collections import Counter
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
from time import perf_counter
from urllib.parse import urlparse

from run_model_evaluation import ROOT,numeric_check
from backend import services,model_runtime,APP_VERSION
from backend.analysis import Spec,analyse
from backend.evidence_tools import ToolPlan,execute

SUITE=ROOT/'evaluation/deepseek-20261019-targeted-v4'


def read(path):return json.loads(path.read_text(encoding='utf-8'))


def preflight():
    if (SUITE/'runs').exists():raise RuntimeError('Retest already started; automatic repeats are forbidden')
    for name,digest in read(SUITE/'freeze.json')['files'].items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=digest:raise RuntimeError('Frozen input changed: '+name)
    cases=read(SUITE/'cases.json')
    if len(cases)!=13 or len({c['case_id'] for c in cases})!=13 or sum(c['category']=='scope_rules' for c in cases)!=6:
        raise RuntimeError('Unexpected targeted retest scope')
    for case in cases:
        if hashlib.sha256((ROOT/case['source_first_result']).read_bytes()).hexdigest()!=case['source_sha256']:
            raise RuntimeError('Source first response changed')
    if APP_VERSION!='0.5.3':raise RuntimeError('Retest is frozen for app 0.5.3')
    return cases


async def run(args,cases):
    refs=read(SUITE/'reference.json');config=services.config()
    if urlparse(config['base_url']).hostname!='api.deepseek.com' or config['model']!='deepseek-flash':
        raise RuntimeError('Budget applies only to saved official DeepSeek Flash endpoint')
    run_id=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ');out=SUITE/'runs'/run_id;out.mkdir(parents=True)
    with model_runtime.budget(args.budget_usd) as ledger:
        summary={'run_id':run_id,'app_version':APP_VERSION,'started_at':datetime.now(timezone.utc).isoformat(),
            'model':services.public_config(),'cases_planned':13,'automatic_retries':0,'budget':ledger,'results':[],
            'evaluation_type':'targeted_exposed_case_retest_not_blind','semantic_review':'pending','independent_human_reviews_completed':0}
        for index,case in enumerate(cases,1):
            if services.config()!=config:raise RuntimeError('Model configuration changed during retest')
            task=case['task'];result=analyse(Spec(**task['spec']))
            if result['data_sha256']!=task['data_sha256']:raise RuntimeError('Data changed')
            started=perf_counter();answer={};trace=[];error=None
            try:
                if case['group']=='pipeline':
                    answer=await services.ask_ai(task['question'],result,persist=False);trace=answer['model_trace']
                else:
                    with model_runtime.capture() as trace:
                        answer=await services.explain_packet(task['question'],execute(result,ToolPlan(**task['baseline_plan'])))
                status=answer['status']
            except Exception as exc:
                if isinstance(exc,model_runtime.BudgetExceeded):raise
                trace=getattr(exc,'model_trace',trace);status='failed'
                error={'type':type(exc).__name__,'message':str(exc)[:1500]}
            checks=numeric_check(answer,refs[task['id']])
            rule_ok=case['category']!='scope_rules' or (answer.get('response_origin')=='scope_rules' and not trace)
            mechanical_pass=status=='answered' and all(n['present_and_correct'] for n in checks) and answer.get('coverage',{}).get('complete',True) and rule_ok
            payload={'case_id':case['case_id'],'category':case['category'],'group':case['group'],'status':status,
                'answer':answer,'trace':trace,'error':error,'elapsed_ms':round((perf_counter()-started)*1000),
                'number_checks':checks,'mechanical_pass':mechanical_pass,'actual_api_requests':len(trace),
                'response_origin':answer.get('response_origin','model' if trace else 'unavailable'),
                'semantic_review':'pending','source_first_result':case['source_first_result']}
            with (out/(case['case_id']+'.first.json')).open('x',encoding='utf-8') as stream:json.dump(payload,stream,ensure_ascii=False,indent=2)
            summary['results'].append({k:payload[k] for k in ['case_id','category','status','number_checks','mechanical_pass','actual_api_requests','response_origin']})
            (out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
            print(f'{index:02d}/13 {case["case_id"]}: {status}, mechanical_pass={mechanical_pass}, requests={len(trace)}',flush=True)
        summary['finished_at']=datetime.now(timezone.utc).isoformat()
        summary['statuses']=dict(Counter(r['status'] for r in summary['results']))
        summary['totals']={'cases':13,'mechanical_pass':sum(r['mechanical_pass'] for r in summary['results']),
            'rule_answers':sum(r['response_origin']=='scope_rules' for r in summary['results']),
            'live_model_answers':sum(r['actual_api_requests']>0 and r['status']=='answered' for r in summary['results']),
            'required_numeric_items':sum(len(r['number_checks']) for r in summary['results']),
            'numeric_items_present_and_correct':sum(n['present_and_correct'] for r in summary['results'] for n in r['number_checks'])}
        if ledger['requests']>11:raise RuntimeError('Unexpected request count exceeds targeted scope')
        (out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
        (SUITE/'latest-run.json').write_text(json.dumps({'run_id':run_id,'summary':(out/'summary.json').relative_to(ROOT).as_posix()},ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps({'run_id':run_id,'totals':summary['totals'],'budget':ledger},ensure_ascii=False),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--execute',action='store_true');parser.add_argument('--budget-usd',type=float,default=0.50)
    args=parser.parse_args()
    if not 0<args.budget_usd<=0.50:parser.error('Targeted budget must be above zero and at most USD 0.50')
    cases=preflight()
    if args.execute:asyncio.run(run(args,cases))
    else:print(json.dumps({'cases':len(cases),'maximum_requests':11,'live_requests':0}))

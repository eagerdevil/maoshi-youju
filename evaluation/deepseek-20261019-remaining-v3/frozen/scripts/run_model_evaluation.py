"""Real API evaluation, no mocks, no retries, immutable per-run first responses."""
import argparse, asyncio, hashlib, json, random, sys
from urllib.parse import urlparse
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path
from time import perf_counter
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'.vendor'));sys.path.insert(0,str(ROOT))
from backend.analysis import Spec, analyse
from backend.evidence_tools import ToolPlan,execute
from backend import services, model_runtime


def numeric_check(answer,reference):
    provided=[n for c in answer.get('claims',[]) for n in c.get('numbers',[])]
    checks=[]
    for required in reference['required_numbers']:
        matches=[n for n in provided if n['citation'] in required.get('accepted_citations',[required['citation']]) and n['field']==required['field']]
        expected=required['expected_fraction']
        def correct(n):
            if expected is None:return n['value'] is None
            if n['value'] is None:return False
            tolerance=Fraction('0.01') if required['field'] in {'base','end','x0','x1'} else Fraction('0.00000001')
            return abs(Fraction(n['value'])-Fraction(expected))<=tolerance
        checks.append({'citation':required['citation'],'field':required['field'],'present_and_correct':any(correct(n) for n in matches)})
    return checks


async def run_with_budget(args,ledger):
    suite=ROOT/'evaluation'/args.suite
    freeze=json.loads((suite/'freeze.json').read_text(encoding='utf-8'))
    for name,digest in freeze['files'].items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=digest:raise RuntimeError('Frozen file changed: '+name)
    if not services.public_config()['configured']:raise RuntimeError('No model configured; no model results generated')
    tasks=json.loads((suite/'tasks.json').read_text(encoding='utf-8'))
    refs=json.loads((suite/'reference.json').read_text(encoding='utf-8'))
    random.Random(20261019).shuffle(tasks)
    if args.limit:tasks=tasks[:args.limit]
    run_id=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    out=suite/'runs'/run_id;out.mkdir(parents=True)
    config=services.config()
    if urlparse(config['base_url']).hostname!='api.deepseek.com' or config['model']!='deepseek-flash':raise RuntimeError('Price budget applies only to the configured official deepseek-flash endpoint')
    summary={'run_id':run_id,'started_at':datetime.now(timezone.utc).isoformat(),'model':services.public_config(),
             'tasks_planned':len(tasks),'groups':['pipeline','fixed_evidence'],'live_api':True,'automatic_retries':0,
             'results':[],'semantic_review':'pending_independent_human_review','budget':ledger}
    for index,task in enumerate(tasks):
        result=analyse(Spec(**task['spec']))
        if result['data_sha256']!=task['data_sha256']:raise RuntimeError('Dataset changed')
        groups=['pipeline','fixed_evidence'] if index%2==0 else ['fixed_evidence','pipeline']
        for group in groups:
            if services.config()!=config:raise RuntimeError('Model configuration changed during evaluation')
            started=perf_counter();answer={};trace=[]
            try:
                if group=='pipeline':answer=await services.ask_ai(task['question'],result,persist=False);trace=answer['model_trace']
                else:
                    with model_runtime.capture() as trace:
                        answer=await services.explain_packet(task['question'],execute(result,ToolPlan(**task['baseline_plan'])))
                    answer['model_trace']=trace
                status=answer['status']
                error=None
            except Exception as exc:
                if isinstance(exc,model_runtime.BudgetExceeded):raise
                trace=getattr(exc,'model_trace',trace)
                status='failed';error={'type':type(exc).__name__}
            payload={'task_id':task['id'],'group':group,'created_at':datetime.now(timezone.utc).isoformat(),
                     'elapsed_ms':round((perf_counter()-started)*1000),'status':status,'answer':answer,'trace':trace,'error':error,
                     'number_checks':numeric_check(answer,refs[task['id']]),
                     'clarification_status_matches':(status==refs[task['id']]['expected_status']) if group=='pipeline' else None,
                     'human_review':{k:None for k in ['citation_support','role_correct','clarification_adequate','no_overclaim']}}
            path=out/(task['id']+'--'+group+'.first.json')
            with path.open('x',encoding='utf-8') as f:json.dump(payload,f,ensure_ascii=False,indent=2)
            summary['results'].append({k:payload[k] for k in ['task_id','group','status','elapsed_ms','number_checks','clarification_status_matches']})
            (out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
            print(f'{len(summary["results"]):02d}/{len(tasks)*2} {group} {task["id"]}: {status}',flush=True)
    summary['finished_at']=datetime.now(timezone.utc).isoformat()
    summary['totals']={}
    for group in summary['groups']:
        rows=[r for r in summary['results'] if r['group']==group]
        numeric=[n for r in rows for n in r['number_checks']]
        summary['totals'][group]={'attempts':len(rows),'protocol_failures':sum(r['status']=='failed' for r in rows),
            'required_numeric_items':len(numeric),'numeric_items_present_and_correct':sum(n['present_and_correct'] for n in numeric),
            'human_semantic_reviews_completed':0}
    (out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    (suite/'latest-run.json').write_text(json.dumps({'run_id':run_id,'summary':str((out/'summary.json').relative_to(ROOT)).replace('\\','/')},ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'run_id':run_id,'totals':summary['totals'],'semantic_review':'pending'},ensure_ascii=False),flush=True)

async def run(args):
    with model_runtime.budget(args.budget_usd) as ledger:
        await run_with_budget(args,ledger)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--suite',choices=['deepseek-20261019-v1','deepseek-20261019-regression-v2'],default='deepseek-20261019-v1')
    parser.add_argument('--limit',type=int,choices=[1,2,3],default=3)
    parser.add_argument('--budget-usd',type=float,default=0.10)
    args=parser.parse_args()
    if not 0 < args.budget_usd <= 0.10:parser.error('Small pilot budget must be above zero and at most USD 0.10')
    asyncio.run(run(args))

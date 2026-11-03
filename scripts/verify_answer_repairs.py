"""Reproduce four repairs offline, using preserved first model outputs unchanged."""
import asyncio
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'.vendor'));sys.path.insert(0,str(ROOT))
from backend import services,APP_VERSION
from backend.analysis import Spec,analyse
from backend.evidence_tools import ToolPlan,execute
from backend.answer_contract import normalize_plan


def read(path):return json.loads(path.read_text(encoding='utf-8'))


async def main():
    suite=ROOT/'evaluation/deepseek-20261019-remaining-v3'
    run=ROOT/Path(read(suite/'latest-run.json')['summary']).parent
    tasks={t['id']:t for t in read(suite/'tasks.json')}
    class NoNetwork:
        def __init__(self,*args,**kwargs):raise RuntimeError('Offline verification must never use a network client')
    services.httpx.AsyncClient=NoNetwork
    cases=[]
    hashes={}
    for path in run.glob('*.first.json'):
        hashes[path.relative_to(ROOT).as_posix()]=hashlib.sha256(path.read_bytes()).hexdigest()
    async def forbidden(messages):raise RuntimeError('Scope rule unexpectedly requested a model')
    services.complete=forbidden
    for key,task in tasks.items():
        if not key.endswith('-role'):continue
        answer=await services.ask_ai(task['question'],analyse(Spec(**task['spec'])),persist=False)
        assert answer['response_origin']=='scope_rules' and answer['status']=='answered' and not answer['model_trace']
        cases.append({'task_id':key,'check':'scope_rules','status':'passed','actual_model_calls':0})
    for suffix in ['numeric','injection','causal','windows']:
        key='de-cn-tea-'+suffix;task=tasks[key]
        source=read(run/(key+'--pipeline.first.json'))
        result=analyse(Spec(**task['spec']))
        effective,changes=normalize_plan(ToolPlan(**json.loads(source['trace'][0]['content'])),result,task['question'])
        packet=execute(result,effective)
        assert all(w['spec']['reporter']=='DEU' and w['spec']['partner']=='CHN' for w in packet['windows'])
        cases.append({'task_id':key,'check':'planner_executable_only','status':'passed','plan_adjustments':changes,
                      'note':'仅证明已保存规划可被规范化并执行，未生成新的真实模型解释。'})
    for key in ['ca-cocoa-numeric','de-cn-tea-windows','export-coffee-windows']:
        task=tasks[key];source=read(run/(key+'--fixed_evidence.first.json'))
        raw=source['trace'][-1]['content']
        async def replay(messages):return raw
        services.complete=replay
        packet=execute(analyse(Spec(**task['spec'])),ToolPlan(**task['baseline_plan']))
        answer=await services.explain_packet(task['question'],packet)
        if key=='export-coffee-windows':
            assert answer['status']=='incomplete' and answer['coverage']['model_covered']==4 and answer['coverage']['required']==6
        else:
            assert answer['status']=='answered' and answer['coverage']['complete']
        cases.append({'task_id':key,'check':'unchanged_raw_response_replay','status':'passed','answer_status':answer['status'],
                      'coverage':answer['coverage'],'field_normalizations':answer['field_normalizations']})
    for name,digest in hashes.items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest
    code={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in
          ['backend/answer_contract.py','backend/services.py','backend/evidence_tools.py','frontend/src/main.tsx']}
    report={'version':APP_VERSION,'verification':'offline_replay_only_not_live_model_retest','actual_model_requests':0,
            'cases':cases,'original_first_outputs_sha256':hashes,'patched_code_sha256':code,
            'note':'未修改旧首次结果或重新评分；模型自然语言语义仍需人工复核，修复后真实调用表现未知。'}
    destination=ROOT/'研究成果/修复核验';destination.mkdir(parents=True,exist_ok=True)
    (destination/'0.5.3离线修复核验.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'version':APP_VERSION,'offline_repair_cases':len(cases),'passed':len(cases),
                      'preserved_original_outputs':len(hashes),'actual_model_requests':0},ensure_ascii=False))


if __name__=='__main__':asyncio.run(main())

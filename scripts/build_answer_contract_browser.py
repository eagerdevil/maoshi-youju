"""Build browser fixtures by offline replay. The browser test blocks all AI requests."""
import asyncio
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'.vendor'));sys.path.insert(0,str(ROOT))
from backend import services
from backend.analysis import Spec,analyse
from backend.evidence_tools import ToolPlan,execute
from backend.answer_contract import scope_answer


def read(path):return json.loads(path.read_text(encoding='utf-8'))


async def main():
    suite=ROOT/'evaluation/deepseek-20261019-remaining-v3'
    run=ROOT/Path(read(suite/'latest-run.json')['summary']).parent
    tasks={t['id']:t for t in read(suite/'tasks.json')}
    class NoNetwork:
        def __init__(self,*args,**kwargs):raise RuntimeError('QA fixtures must never call a model')
    services.httpx.AsyncClient=NoNetwork
    fixtures={}
    for key,label in [('export-coffee-windows','incomplete'),('ca-cocoa-numeric','ratio')]:
        task=tasks[key];result=analyse(Spec(**task['spec']))
        packet=execute(result,ToolPlan(**task['baseline_plan']))
        raw=read(run/(key+'--fixed_evidence.first.json'))['trace'][-1]['content']
        async def replay(messages):return raw
        services.complete=replay
        answer=await services.explain_packet(task['question'],packet)
        answer.update(model='离线回放（未调用模型）',provider='offline_replay',model_trace=[])
        fixtures[label]={'result':result,'answer':answer,'question':task['question']}
        fixtures['scope']={'result':result,'answer':scope_answer(result,execute(result,ToolPlan(tool='overview'))),
                           'question':'请明确当前报告国、伙伴角色和贸易流向，并说明统计金额含义'}
    targeted=ROOT/'evaluation/deepseek-20261019-targeted-v4'
    new_run=ROOT/Path(read(targeted/'latest-run.json')['summary']).parent
    for key,label,pipeline in [('ca-cocoa-numeric','verbose','fixed_evidence'),('de-cn-tea-injection','wording','pipeline')]:
        task=tasks[key];result=analyse(Spec(**task['spec']))
        packet=execute(result,ToolPlan(**task['baseline_plan']))
        raw=read(new_run/(key+'--'+pipeline+'.first.json'))['trace'][-1]['content']
        async def replay(messages):return raw
        services.complete=replay
        answer=await services.explain_packet(task['question'],packet)
        answer.update(model='离线回放（未调用模型）',provider='offline_replay',model_trace=[])
        fixtures[label]={'result':result,'answer':answer,'question':task['question']}
    destination=ROOT/'output/playwright';destination.mkdir(parents=True,exist_ok=True)
    serialized=json.dumps(fixtures,ensure_ascii=False)
    (destination/'answer-contract-fixtures.json').write_text(serialized,encoding='utf-8')
    script=(ROOT/'scripts/check_answer_contract_browser.js').read_text(encoding='utf-8')
    (destination/'check-answer-contract.generated.js').write_text(script.replace('__ANSWER_CONTRACT_FIXTURES__',serialized),encoding='utf-8')
    print('Browser fixtures generated offline; network client is disabled')


if __name__=='__main__':asyncio.run(main())

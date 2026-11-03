"""Replay real first failures offline; no API calls, no rewriting original results."""
import asyncio
import json
from pathlib import Path

import pytest

from backend import services
from backend.analysis import Spec, analyse
from backend.answer_contract import is_scope_question, normalize_plan
from backend.data import DataError
from backend.evidence_tools import ToolPlan, execute, bind_numbers

ROOT = Path(__file__).resolve().parents[1]
SUITE = ROOT / 'evaluation/deepseek-20261019-remaining-v3'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


@pytest.fixture(scope='module')
def frozen():
    run = ROOT / Path(read(SUITE / 'latest-run.json')['summary']).parent
    tasks = {t['id']: t for t in read(SUITE / 'tasks.json')}
    return tasks, run


def no_network(*args, **kwargs):
    pytest.fail('Offline repair verification must not call a model')


@pytest.mark.parametrize('prefix',['gb-tea','us-coffee','cn-cars','ca-cocoa','export-coffee','de-cn-tea'])
def test_current_scope_questions_need_no_model_or_clarification(frozen, monkeypatch, prefix):
    task=frozen[0][prefix+'-role']
    result=analyse(Spec(**task['spec']))
    monkeypatch.setattr(services,'complete',no_network)
    answer=asyncio.run(services.ask_ai(task['question'],result,persist=False))
    assert answer['status']=='answered' and answer['response_origin']=='scope_rules'
    assert answer['provider']=='deterministic' and not answer['model_trace']
    assert answer['claims'][0]['citations']
    assert 'CIF' not in json.dumps(answer['claims'])


def test_scope_rule_does_not_swallow_new_year_or_country_or_numeric_question():
    result=analyse(Spec())
    for question in ['说明当前报告国，并给出2024年的金额','当前报告国换成日本，说明贸易流向',
                     '说明当前报告国，并比较巴西增长率','说明当前报告国，并给出具体金额',
                     '请说明当前报告国与巴西的贸易流向']:
        assert not is_scope_question(question,result)


@pytest.mark.parametrize('suffix',['numeric','injection','causal','windows'])
def test_real_bilateral_failed_plans_keep_same_pair_and_execute(frozen,suffix):
    tasks,run=frozen
    key='de-cn-tea-'+suffix
    first=read(run/(key+'--pipeline.first.json'))
    result=analyse(Spec(**tasks[key]['spec']))
    plan=ToolPlan(**json.loads(first['trace'][0]['content']))
    effective,changes=normalize_plan(plan,result,tasks[key]['question'])
    assert changes and effective.partners==[]
    packet=execute(result,effective)
    assert all(w['spec']['reporter']=='DEU' and w['spec']['partner']=='CHN' for w in packet['windows'])
    assert len(packet['windows'])==(2 if suffix=='windows' else 1)


def test_bilateral_normalizer_never_changes_to_an_unselected_partner():
    result=analyse(Spec(mode='bilateral',reporter='DEU',partner='CHN'))
    with pytest.raises(DataError,match='不能自动改成其他伙伴'):
        normalize_plan(ToolPlan(tool='partner',partners=['JPN']),result,'分析日本')


def test_explicit_chinese_windows_are_not_silently_omitted():
    result=analyse(Spec(mode='comparison',flow='X',products=['0901']))
    plan,changes=normalize_plan(ToolPlan(tool='comparison'),result,'固定报告期，分别以二〇一九年和二〇二二年为基期比较区间增长率')
    assert plan.tool=='window_compare' and plan.base_years==[2019,2022] and changes
    for question in ['分别以二〇一九年和二〇二四年为基期比较','分别以二〇一九年和二〇二三年为基期比较']:
        invalid,_=normalize_plan(ToolPlan(tool='overview'),result,question)
        with pytest.raises(DataError,match='基期'):
            execute(result,invalid)


def replay_explanation(frozen,monkeypatch,key):
    tasks,run=frozen
    source=read(run/(key+'--fixed_evidence.first.json'))
    task=tasks[key]
    packet=execute(analyse(Spec(**task['spec'])),ToolPlan(**task['baseline_plan']))
    observed=[]
    async def replay(messages):
        observed.append(messages)
        return source['trace'][-1]['content']
    monkeypatch.setattr(services,'complete',replay)
    answer=asyncio.run(services.explain_packet(task['question'],packet))
    return answer,observed


@pytest.mark.parametrize('key',['ca-cocoa-numeric','de-cn-tea-windows'])
def test_real_invalid_field_outputs_resolve_to_existing_evidence(frozen,monkeypatch,key):
    answer,observed=replay_explanation(frozen,monkeypatch,key)
    assert answer['status']=='answered' and answer['field_normalizations']
    assert answer['coverage']['complete']
    registry={e['id']:e for e in answer['evidence']}
    for claim in answer['claims']:
        for n in claim['numbers']:
            e=registry[n['citation']]
            assert n['value']==(e['result'] if n['field']=='result' else e['operands'][n['field']])
            if n['field'] in {'s0','s1'}:
                assert n['unit']=='比例'
    context=json.loads(observed[0][1]['content'])['result']
    assert context['numeric_field_catalogue'] and context['required_numeric_items']


def test_real_six_window_answer_is_marked_incomplete_and_all_evidence_is_shown(frozen,monkeypatch):
    answer,_=replay_explanation(frozen,monkeypatch,'export-coffee-windows')
    assert answer['status']=='incomplete'
    assert answer['coverage']['required']==6 and answer['coverage']['model_covered']==4
    assert len(answer['coverage']['rows'])==6 and len(answer['coverage']['missing'])==2
    assert {(r['object'],r['base_year']) for r in answer['coverage']['missing']}=={('英国',2019),('德国',2022)}
    assert len(answer['claims'])==4  # No program-written claims are disguised as model output.


def test_six_claims_cover_all_country_window_combinations(frozen,monkeypatch):
    task=frozen[0]['export-coffee-windows']
    packet=execute(analyse(Spec(**task['spec'])),ToolPlan(**task['baseline_plan']))
    async def fake(messages):
        context=json.loads(messages[1]['content'])['result']
        return json.dumps({'claims':[{'text':'该窗口的区间增长率见证据。','citations':[r['citation']],
                                     'numbers':[{'citation':r['citation'],'field':r['field']}]} for r in context['required_numeric_items']]})
    monkeypatch.setattr(services,'complete',fake)
    answer=asyncio.run(services.explain_packet(task['question'],packet))
    assert len(answer['claims'])==6 and answer['status']=='answered'
    assert answer['coverage']['required']==answer['coverage']['model_covered']==6


def test_field_aliases_do_not_accept_arbitrary_paths_or_model_values():
    result=analyse(Spec(products=['8703']))
    packet=execute(result,ToolPlan(tool='partner',partners=['JPN']))
    registry={e['id']:e for e in packet['evidence']}
    cid=packet['windows'][0]['partners'][0]['evidence_id']
    for field in ['operands.made_up','records.0.value','share2','__dict__']:
        with pytest.raises(DataError):
            bind_numbers([{'citation':cid,'field':field}],[cid],registry)
    with pytest.raises(DataError,match='禁止模型填写数值'):
        bind_numbers([{'citation':cid,'field':'operands.x0','value':999}],[cid],registry)


def test_two_share_levels_require_both_ratios_not_share_change():
    from backend.answer_contract import required_numbers
    result=analyse(Spec(products=['8703']))
    packet=execute(result,ToolPlan(tool='partner',partners=['JPN']))
    rows=required_numbers('日本基期与报告期的份额分别是多少？',packet)
    assert [r['field'] for r in rows]==['s0','s1']
    assert all(r['unit']=='比例' for r in rows)


def test_targeted_real_verbose_answer_has_short_view_without_losing_coverage():
    from backend.answer_contract import required_numbers, answer_presentation, check_coverage
    suite = ROOT / 'evaluation/deepseek-20261019-targeted-v4'
    run = ROOT / Path(read(suite / 'latest-run.json')['summary']).parent
    source = read(run / 'ca-cocoa-numeric--fixed_evidence.first.json')
    # Preserve the sealed record; replay just its raw model explanation.
    task = next(t for t in read(SUITE / 'tasks.json') if t['id'] == 'ca-cocoa-numeric')
    packet = execute(analyse(Spec(**task['spec'])), ToolPlan(**task['baseline_plan']))
    registry = {e['id']: e for e in packet['evidence']}
    raw = json.loads(source['trace'][-1]['content'])
    claims = raw['claims']
    for c in claims:
        c['numbers'] = bind_numbers(c['numbers'], c['citations'], registry)
    required = required_numbers(task['question'], packet)
    view = answer_presentation(task['question'], claims, raw['limitations'], required, registry)
    selected = [claims[i] for i in view['primary_claim_indices']]
    assert len(claims) == 14 and len(selected) < len(claims)
    assert check_coverage(required, selected, registry)['complete']
    assert sorted(view['primary_claim_indices'] + view['additional_claim_indices']) == list(range(14))


@pytest.mark.parametrize('text,flagged', [
    ('所谓增长九百九十九个百分点的说法与证据不符', True),
    ('金额增长了五个百分点', True),
    ('份额增长五个百分点，不能证明政策因果', False),
    ('增长率之差为五个百分点', False),
    ('题述增长率与证据不符', False),
])
def test_percentage_point_wording_guard_preserves_original(text, flagged):
    from backend.answer_contract import answer_presentation
    claims = [{'text': text, 'numbers': [], 'citations': []}]
    view = answer_presentation('解释增长率', claims, [text], [], {})
    assert bool(view['wording_warnings']) == flagged
    assert claims[0]['text'] == text
    if flagged:
        assert {w['section'] for w in view['wording_warnings']} == {'claims', 'limitations'}


def test_causal_question_does_not_collapse_model_explanation():
    from backend.answer_contract import answer_presentation
    claims = [{'text': '这不足以证明政策因果', 'numbers': [], 'citations': []}]
    view = answer_presentation('增长率能证明政策有效吗？', claims, [], [{'field': 'growth_percent'}], {})
    assert view['primary_claim_indices'] == [0] and not view['additional_claim_indices']

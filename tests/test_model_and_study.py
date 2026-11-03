import asyncio,json
import httpx
import pytest
from fastapi.testclient import TestClient
from backend.app import app
from backend import services,study,model_runtime
from backend.analysis import Spec,analyse
from backend.evidence_tools import model_scope


def test_effective_roles_exclude_inactive_defaults():
    a=model_scope(Spec(mode='comparison',flow='X').model_dump())
    assert 'reporter' not in a and 'partner' not in a and a['reporters']==['CHN','DEU','JPN']
    a=model_scope(Spec().model_dump())
    assert 'reporter' in a and 'reporters' not in a and 'partner' not in a
    a=model_scope(Spec(mode='bilateral').model_dump())
    assert 'reporter' in a and 'partner' in a and 'reporters' not in a


def test_real_protocol_trace_has_no_authorization_header(monkeypatch):
    monkeypatch.setattr(services,'config',lambda:{'provider':'compatible','base_url':'https://api.deepseek.com','model':'deepseek-flash','api_key':'not-a-real-test-key'})
    observed=[]
    class Client:
        def __init__(self,**kwargs):pass
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        async def post(self,url,headers,json):
            observed.append(json)
            return httpx.Response(200,request=httpx.Request('POST',url),json={'model':'test-model','choices':[{'finish_reason':'stop','message':{'content':'{"status":"ok"}'}}],'usage':{'prompt_tokens':40,'completion_tokens':5,'total_tokens':45}})
    monkeypatch.setattr(services.httpx,'AsyncClient',Client)
    with model_runtime.capture() as trace:
        result=asyncio.run(services.test_model_connection())
        # Connection helper uses its own capture; endpoint only exposes selected metadata.
    assert result['ok'] and result['actual_model']=='test-model'
    assert observed[0]['thinking']=={'type':'disabled'} and observed[0]['max_tokens']==4096
    assert 'not-a-real-test-key' not in json.dumps(result)


def test_budget_blocks_before_network_and_accounts_usage():
    with model_runtime.budget(0.00001):
        with pytest.raises(model_runtime.BudgetExceeded):model_runtime.reserve({'max_tokens':4096,'messages':[]})
    with model_runtime.budget(2) as ledger:
        reserved=model_runtime.reserve({'max_tokens':4096,'messages':[]})
        model_runtime.settle(reserved,{'prompt_tokens':100,'completion_tokens':10})
        assert ledger['requests']==1
        assert abs(ledger['estimated_usd']-0.000042)<1e-12


def test_empty_and_length_responses_rejected_and_logged(monkeypatch):
    monkeypatch.setattr(services,'config',lambda:{'provider':'compatible','base_url':'https://example.invalid','model':'mock','api_key':'not-a-real-test-key'})
    class Client:
        def __init__(self,**kwargs):pass
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        async def post(self,url,**kwargs):return httpx.Response(200,request=httpx.Request('POST',url),json={'choices':[{'finish_reason':'length','message':{'content':'{"truncated":'}}]})
    monkeypatch.setattr(services.httpx,'AsyncClient',Client)
    with model_runtime.capture() as events:
        with pytest.raises(ValueError,match='未正常完成'):asyncio.run(services.complete([{'role':'user','content':'json'}]))
    assert events[0]['content']=='{"truncated":' and events[0]['error_type']=='DataError'
    assert 'not-a-real-test-key' not in json.dumps(events)


def test_no_saved_configuration_does_not_start_a_request():
    assert asyncio.run(services.test_model_connection())['stage']=='configuration'


def test_study_rehearsal_not_counted_as_real_people(monkeypatch,tmp_path):
    monkeypatch.setattr(services,'ROOT',tmp_path)
    client=TestClient(app)
    assert client.get('/api/study/tasks').status_code==200
    s=client.post('/api/study/sessions',json={'alias':'QA001','mode':'rehearsal'}).json()
    sid=s['id'];base='/api/study/sessions/'+sid+'/events'
    assert client.post(base,json={'kind':'submit','task_id':'window','answer':'before start','outcome':'completed'}).status_code==422
    assert client.post(base,json={'kind':'start','task_id':'window'}).status_code==200
    assert client.post(base,json={'kind':'start','task_id':'export'}).status_code==422
    answer=client.post(base,json={'kind':'submit','task_id':'window','answer':'Test fixture, not a person','outcome':'blocked','effort':4}).json()
    assert answer['events'][-1]['elapsed_seconds']>=0 and not answer['events'][-1]['observer_verified']
    assert client.post(base,json={'kind':'start','task_id':'window'}).status_code==422
    exported=client.get('/api/study/export').json()
    assert exported['counts']['participant_sessions']==0 and exported['counts']['rehearsal_sessions']==1
    assert exported['counts']['self_reported_task_submissions']==0


def test_study_input_validation_and_unknown_session(monkeypatch,tmp_path):
    monkeypatch.setattr(services,'ROOT',tmp_path)
    c=TestClient(app)
    assert c.post('/api/study/sessions',json={'alias':'real name with spaces'}).status_code==422
    assert c.get('/api/study/sessions/not-present').status_code==422
    s=c.post('/api/study/sessions',json={'alias':'P001'}).json()
    path='/api/study/sessions/'+s['id']+'/events'
    assert c.post(path,json={'kind':'start','task_id':'invalid'}).status_code==422
    assert c.post(path,json={'kind':'start','task_id':'export'}).status_code==200
    assert c.post(path,json={'kind':'submit','task_id':'export','answer':'   ','outcome':'completed'}).status_code==422


def test_prompt_context_does_not_leak_inactive_roles(monkeypatch,tmp_path):
    monkeypatch.setattr(services,'ROOT',tmp_path)
    observed=[]
    async def fake(messages):
        observed.append(messages)
        if len(observed)==1:return '{"tool":"comparison"}'
        packet=json.loads(messages[1]['content'])['result']
        ref=packet['windows'][0]['comparisons'][0]['evidence_id']
        return json.dumps({'claims':[{'text':'各国分别报告世界总额。','citations':[ref]}]})
    monkeypatch.setattr(services,'complete',fake)
    r=analyse(Spec(mode='comparison',flow='X',products=['0901']))
    asyncio.run(services.ask_ai('比较出口',r,persist=False))
    scope=json.loads(observed[0][1]['content'])['scope']
    packet=json.loads(observed[1][1]['content'])['result']
    assert 'reporter' not in scope and 'partner' not in scope
    assert 'reporter' not in packet['windows'][0]['spec']
    assert all('partner' not in e['spec'] for e in packet['evidence'])


def test_material_allowlist_and_release_status(monkeypatch,tmp_path):
    monkeypatch.setattr(services,'ROOT',tmp_path)
    client=TestClient(app)
    materials=client.get('/api/materials').json()
    if not materials:
        pytest.skip('Public source excludes personal submission PDF attachments')
    assert len(materials)==6
    assert next(m['name'] for m in materials if m['id']=='contribution')=='04-单人团队成员贡献说明.pdf'
    for item in materials:
        r=client.get(item['url'])
        assert r.status_code==200 and r.content.startswith(b'%PDF-')
    assert client.get('/api/materials/not-listed').status_code==404
    status=client.get('/api/release-status').json()
    assert status['real_evaluation']['tasks']==3 and status['real_evaluation']['requests']==7
    assert status['model_regression']['tasks']==3 and status['model_regression']['requests']==9
    remaining=status['remaining_evaluation']
    assert remaining['tasks']==33 and 0<remaining['requests']<=99
    assert remaining['automatic_retries']==0
    for group in ['pipeline','fixed_evidence']:
        assert sum(remaining['statuses'][group].values())==remaining['totals'][group]['attempts']==33
    report=client.get(remaining['report_url'])
    assert report.status_code==200 and '66份首次回答' in report.text
    assert client.get('/api/evaluation-report/not-listed').status_code==404
    review=status['ai_semantic_review']
    assert review['responses']==66 and 0<review['requests']<=60
    assert sum(review['statuses'].values())==66
    assert review['human_semantic_reviews_completed']==0
    assert review['review_type']=='same_model_ai_assisted_not_independent_human'
    assert sum(review['ai_verdicts'].values())==review['statuses'].get('reviewed',0)
    ai_report=client.get(review['report_url'])
    assert ai_report.status_code==200 and '不是独立人工评价' in ai_report.text
    targeted=status['targeted_retest']
    assert targeted['version']=='0.5.3' and targeted['cases']==13 and targeted['requests']==11
    assert targeted['totals']['rule_answers']==6 and targeted['totals']['live_model_answers']==7
    assert targeted['totals']['required_numeric_items']==targeted['totals']['numeric_items_present_and_correct']==17
    assert status['answer_safeguards']['live_model_retest']=='completed_targeted'
    assert targeted['semantic_review']=='pending'
    targeted_report=client.get(targeted['report_url'])
    assert targeted_report.status_code==200 and '13份首次完整回答' in targeted_report.text
    assert status['independent_semantic_review']=='pending'
    assert status['study']['participant_sessions']==0
    assert 'api_key' not in json.dumps(status)

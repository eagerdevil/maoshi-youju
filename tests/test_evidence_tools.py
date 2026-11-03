"""Protocol mocks test validation only, not live model accuracy."""
import asyncio
import json
import pytest
from fastapi.testclient import TestClient
from backend.analysis import Spec, analyse
from backend.app import app
from backend import services
from backend.data import DataError
from backend.evidence_tools import ToolPlan, execute, bind_numbers


@pytest.fixture(scope='module')
def main():
    return analyse(Spec(products=['8703']))


def test_named_japan_not_lost_to_top_eight(main):
    p=execute(main,ToolPlan(tool='partner',partners=['JPN']))
    japan=p['windows'][0]['partners'][0]
    assert japan['code']=='JPN' and japan['share_change']<0 and japan['growth']>0
    assert japan['evidence_id']==main['analysis_id']+':E0058'


def test_canada_reversal_and_namespaced_evidence(main):
    p=execute(main,ToolPlan(tool='window_compare',partners=['CAN'],base_years=[2019,2022]))
    a,b=p['windows']
    assert a['partners'][0]['share_change']<0<b['partners'][0]['share_change']
    assert a['analysis_id']!=b['analysis_id']
    ids={e['id'] for e in p['evidence']}
    assert all(w['partners'][0]['evidence_id'] in ids for w in p['windows'])
    for e in p['evidence']: assert e['id'].startswith(e['analysis_id']+':')


def test_missing_gibraltar_is_not_exit(main):
    p=execute(main,ToolPlan(tool='partner',partners=['GIB']))
    row=p['windows'][0]['partners'][0]
    assert row['current'] is None and row['growth'] is None and row['status']=='unknown'
    e=next(e for e in p['evidence'] if e['id']==row['evidence_id'])
    assert e['operands']['x1'] is None and e['result'] is None


def test_three_partners_four_windows_match_engine(main):
    p=execute(main,ToolPlan(tool='window_compare',partners=['KOR','DEU','CAN'],base_years=[2019,2020,2021,2022]))
    for w in p['windows']:
        expected=analyse(Spec(**w['spec']))
        assert expected['analysis_id']==w['analysis_id']
        for row in w['partners']:
            original=next(x for x in expected['partners'] if x['code']==row['code'])
            assert original['share_change']==row['share_change']


@pytest.mark.parametrize('args',[
    {'tool':'partner'}, {'tool':'partner','partners':['WLD']},
    {'tool':'partner','partners':['CAN','CAN']},
    {'tool':'window_compare','base_years':[2018]},
    {'tool':'window_compare','base_years':[2023]},
    {'tool':'window_compare','base_years':[2022,2022]},
    {'tool':'overview','base_years':[2020]},
])
def test_invalid_tools_rejected(main,args):
    with pytest.raises(DataError):execute(main,ToolPlan(**args))


def test_tools_available_without_model_and_reject_stale_version(main):
    client=TestClient(app)
    body={'spec':main['spec'],'plan':{'tool':'partner','partners':['JPN']},'expected_analysis_id':main['analysis_id']}
    assert client.post('/api/tools/execute',json=body).status_code==200
    body['expected_analysis_id']='stale'
    assert client.post('/api/tools/execute',json=body).status_code==422
    assert client.post('/api/ai/ask',json={'spec':main['spec'],'question':'分析','expected_analysis_id':'stale'}).status_code==422


def test_bound_missing_and_exact_decimal(main):
    p=execute(main,ToolPlan(tool='partner',partners=['GIB']))
    registry={e['id']:e for e in p['evidence']}
    ref=p['windows'][0]['partners'][0]['evidence_id']
    bound=bind_numbers([{'citation':ref,'field':'x0'},{'citation':ref,'field':'x1'}],[ref],registry)
    assert bound[0]['value']==registry[ref]['operands']['x0']
    assert bound[1]['value'] is None


@pytest.mark.parametrize('bad',[
    {'citation':'E0058','field':'x1'},
    {'citation':'valid','field':'invented'},
    {'citation':'valid','field':'x1','value':999},
])
def test_bad_number_bindings_rejected(main,bad):
    p=execute(main,ToolPlan(tool='partner',partners=['JPN']))
    ref=p['windows'][0]['partners'][0]['evidence_id']
    if bad['citation']=='valid':bad=bad|{'citation':ref}
    with pytest.raises(DataError):bind_numbers([bad],[ref],{e['id']:e for e in p['evidence']})


def test_mock_ai_uses_selected_windows_and_bound_values(main,monkeypatch,tmp_path):
    monkeypatch.setattr(services,'ROOT',tmp_path)
    monkeypatch.setattr(services,'config',lambda:{'model':'protocol-mock','provider':'mock'})
    observed=[]
    async def fake(messages):
        observed.append(messages)
        if len(observed)==1:return json.dumps({'tool':'window_compare','partners':['CAN'],'base_years':[2019,2022]})
        packet=json.loads(messages[1]['content'])['result']
        refs=[w['partners'][0]['evidence_id'] for w in packet['windows']]
        return json.dumps({'claims':[{'text':'加拿大的份额变化方向随基期改变。','citations':refs,'numbers':[{'citation':r,'field':'share_change_pp'} for r in refs]}],'limitations':['描述性变化不能证明因果。']})
    monkeypatch.setattr(services,'complete',fake)
    answer=asyncio.run(services.ask_ai('比较加拿大不同基期的份额变化',main))
    values=answer['claims'][0]['numbers']
    assert float(values[0]['value'])<0<float(values[1]['value'])
    assert len(answer['windows'])==2 and answer['evidence']
    assert all('records' not in e for e in json.loads(observed[1][1]['content'])['result']['evidence'])

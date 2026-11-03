import hashlib
import io
import json
import subprocess
import sys
import zipfile
from decimal import Decimal
from fractions import Fraction
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from backend.analysis import Spec, analyse
from backend.app import app
from backend.data import DataError, get_dataset
from backend.diagnostics import diagnose, direction, quadrant, report
from backend import services


@pytest.fixture(scope='module')
def main():
    return analyse(Spec(products=['8703']))


@pytest.fixture(scope='module')
def diagnostic(main):
    return diagnose(main)


def entity(d, code): return next(r for r in d['rows'] if r['code']==code)


@pytest.mark.parametrize('values,expected',[
    (['1','2'],'positive'), (['-1','-2'],'negative'), (['0','0'],'flat'),
    (['0','2'],'with_flat'), (['1','-1'],'reversal'), (['1',None],'insufficient'),
    (['1'],'insufficient'), (['0'],'insufficient'), (['1','-1',None],'reversal'),
    (['0.0000000000001','-0.0000000000001'],'reversal'),
])
def test_exact_direction_rules(values,expected):
    assert direction(values)==expected


def test_canada_reversal_japan_divergence_and_missing(diagnostic):
    can=entity(diagnostic,'CAN'); jpn=entity(diagnostic,'JPN'); gib=entity(diagnostic,'GIB')
    assert can['direction']=='reversal' and can['complete']
    assert float(can['points'][0]['metric'])<0<float(can['points'][-1]['metric'])
    assert jpn['quadrant']=='amount_up_share_down'
    assert gib['direction']=='insufficient' and not gib['complete']
    assert all(p['metric'] is None for p in gib['points'])
    assert gib['primary']['baseline'] is not None and gib['primary']['current'] is None


def test_selected_windows_have_different_diagnostic_identity(main):
    a=diagnose(main,[2019,2022]); b=diagnose(main,[2020,2021])
    assert a['diagnostic_id']!=b['diagnostic_id']
    assert diagnose(main,[2022,2019])==a
    assert a['analysis_id']==b['analysis_id']==main['analysis_id']


def test_all_metrics_match_independent_fraction_reference(diagnostic):
    rows,_,_=get_dataset('wits-core')
    values={(r['partner'],r['year']):Fraction(r['value']) for r in rows if r['reporter']=='USA' and r['flow']=='M' and r['product']=='8703' and r['value'] is not None}
    for code in ['KOR','DEU','CAN','JPN']:
        row=entity(diagnostic,code)
        for point in row['points']:
            expected=(values[code,2023]/values['WLD',2023]-values[code,point['base_year']]/values['WLD',point['base_year']])*100
            assert abs(float(point['metric'])-float(expected))<1e-12


def test_all_citations_bind_correct_window_and_metric(diagnostic):
    index={e['id']:e for e in diagnostic['evidence']}
    assert len(index)==len(diagnostic['evidence'])
    for row in diagnostic['rows']:
        for p in row['points']:
            if p['evidence_id']:
                e=index[p['evidence_id']]
                assert p['analysis_id']==e['analysis_id'] and p['base_year']==e['spec']['base_year']
                assert p['metric']==e['operands']['share_change_pp']
                assert p['delta']==e['result']


@pytest.mark.parametrize('years',[[2018,2022],[2023],[2019,2019],[],[2019,2020,2021,2022,2023,2024,2025]])
def test_invalid_window_selection(main,years):
    with pytest.raises(DataError):diagnose(main,years)


def test_single_window_is_not_called_consistent(main):
    d=diagnose(main,[2022])
    assert d['counts']['consistent']==0 and d['counts']['reversal']==0
    assert entity(d,'CAN')['direction']=='insufficient'


def test_current_window_retained_when_excluded_from_sensitivity(main):
    d=diagnose(main,[2021,2022]);jpn=entity(d,'JPN')
    assert jpn['primary']['base_year']==2019
    assert jpn['quadrant']=='amount_up_share_down'
    assert [p['base_year'] for p in jpn['points']]==[2021,2022]
    assert jpn['primary']['evidence_id'] in {e['id'] for e in d['evidence']}


@pytest.mark.parametrize('spec',[
    Spec(mode='comparison',flow='X',products=['8703']),
    Spec(mode='bilateral',reporter='USA',partner='CHN',products=['0901','0902']),
    Spec(dataset_id='wits-canada-cocoa',reporter='CAN',products=['1806']),
])
def test_three_modes_and_second_industry(spec):
    result=analyse(spec); d=diagnose(result,[2019,2022])
    assert d['rows'] and len(d['windows'])==2
    if spec.mode!='competition':
        assert d['metric']=='growth_percent' and d['unit']=='%'
        assert all(r['quadrant'] is None for r in d['rows'])
    for row in d['rows']:
        for p in row['points']:
            if p['metric'] is not None:
                assert p['baseline'] is not None and p['current'] is not None


def test_no_source_mutation_and_version_guard(main):
    raw,manifest,sha=get_dataset('wits-core')
    original=json.dumps(main,sort_keys=True)
    diagnose(main,[2019,2022],(raw,manifest,sha))
    assert json.dumps(main,sort_keys=True)==original
    with pytest.raises(DataError,match='版本'):diagnose(main,injected=(raw,manifest,'changed'))


def test_zero_baseline_growth_is_missing_and_no_false_entry(main):
    raw,manifest,sha=get_dataset('wits-core')
    for row in raw:
        if row['reporter']=='USA' and row['partner']=='CHN' and row['product']=='8703' and row['flow']=='M' and row['year']==2019:
            row['value']=Decimal(0)
    spec=Spec(mode='bilateral',products=['8703'])
    r=analyse(spec,(raw,manifest,sha));d=diagnose(r,[2019,2022],(raw,manifest,sha))
    assert d['rows'][0]['points'][0]['metric'] is None
    assert d['rows'][0]['points'][0]['delta'] is not None
    assert not d['rows'][0]['complete'] and d['rows'][0]['direction']=='insufficient'
    assert quadrant('1',None)=='insufficient' and quadrant('0','1')=='flat'


def test_api_no_model_and_outdated_analysis_rejected(main):
    client=TestClient(app)
    body={'spec':main['spec'],'expected_analysis_id':main['analysis_id'],'base_years':[2019,2022]}
    response=client.post('/api/diagnostics',json=body)
    assert response.status_code==200 and response.json()['counts']['reversal']>0
    assert client.post('/api/diagnostics',json=body|{'expected_analysis_id':'stale'}).status_code==422
    assert client.post('/api/diagnostics',json=body|{'base_years':[2023]}).status_code==422
    assert client.post('/api/diagnostics',json=body|{'unknown':True}).status_code==422


def test_offline_report_links_and_html_escaping(diagnostic):
    from html.parser import HTMLParser
    class Links(HTMLParser):
        def __init__(self):super().__init__();self.ids=set();self.refs=[]
        def handle_starttag(self,tag,attrs):
            a=dict(attrs)
            if 'id' in a:self.ids.add(a['id'])
            if a.get('href','').startswith('#'):self.refs.append(a['href'][1:])
    text=report(diagnostic); parser=Links();parser.feed(text)
    assert parser.refs and all(ref in parser.ids for ref in parser.refs)
    unsafe=diagnostic|{'title':'<script>bad</script>'}
    text=report(unsafe)
    assert '<script>' not in text and '&lt;script&gt;' in text
    assert '金额上升、份额下降' in text


def test_diagnostic_bundle_actual_reproduction(main,tmp_path):
    d=diagnose(main,[2019,2022]);data=services.export_diagnostic_zip(main,d)
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        hashes=json.loads(z.read('checksums.json'))
        assert all(hashlib.sha256(z.read(n)).hexdigest()==h for n,h in hashes.items())
        assert json.loads(z.read('diagnostic.json'))==d
        assert not any('config.local' in n or 'app.sqlite' in n for n in z.namelist())
        z.extractall(tmp_path)
    root=Path(__file__).resolve().parents[1]
    command=[sys.executable,'-X','utf8','-c',f"import sys,runpy;sys.path.insert(0,{str(root/'.vendor')!r});runpy.run_path('reproduce_diagnostic.py',run_name='__main__')"]
    completed=subprocess.run(command,cwd=tmp_path,capture_output=True,text=True,encoding='utf-8',timeout=45)
    assert completed.returncode==0,completed.stdout+completed.stderr
    assert 'all diagnostic windows and evidence reproduced' in completed.stdout

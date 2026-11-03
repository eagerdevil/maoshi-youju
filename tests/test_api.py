import io, json, zipfile
import pytest
from fastapi.testclient import TestClient
from backend.app import app
from backend.analysis import Spec, analyse
from backend import services

client=TestClient(app)

def test_health_and_catalogue():
    assert client.get('/api/health').json()['status']=='ok'
    c=client.get('/api/datasets/wits-core').json()
    assert c['rows']==15506 and len(c['coverage'])==30

def test_api_validation_and_no_path_traversal():
    assert client.post('/api/analyse',json={'base_year':2023,'end_year':2019}).status_code==422
    assert client.get('/api/datasets/..%5cconfig.local').status_code in {404,422}

def test_analysis_and_no_model_state(monkeypatch,tmp_path):
    monkeypatch.setattr(services,'CONFIG',tmp_path/'config.json')
    r=client.post('/api/analyse',json=Spec().model_dump());assert r.status_code==200
    unavailable=client.post('/api/ai/ask',json={'question':'分析变化','spec':Spec().model_dump()})
    assert unavailable.status_code==422 and '尚未连接' in unavailable.json()['detail']

def test_model_key_write_only(monkeypatch,tmp_path):
    monkeypatch.setattr(services,'CONFIG',tmp_path/'config.json')
    r=client.post('/api/model',json={'provider':'compatible','base_url':'https://example.org/v1','model':'test-model','api_key':'test-not-real-secret'})
    assert r.status_code==200
    assert 'test-not-real-secret' not in r.text
    assert 'api_key' not in client.get('/api/model').text

def test_report_escapes_user_content():
    r=analyse(Spec());r['title']='<script>alert(1)</script>'
    text=services.report(r)
    assert '<script>' not in text and '&lt;script&gt;' in text

def test_zip_fingerprints_and_no_secrets():
    import hashlib
    response=client.post('/api/export/bundle',json=Spec().model_dump());assert response.status_code==200
    with zipfile.ZipFile(io.BytesIO(response.content)) as z:
        hashes=json.loads(z.read('checksums.json'))
        for name,digest in hashes.items():assert hashlib.sha256(z.read(name)).hexdigest()==digest
        assert not any('config.local' in n or 'app.sqlite' in n for n in z.namelist())
        assert 'reproduce.py' in z.namelist() and 'report.html' in z.namelist()

def test_ai_rejects_unverified_citation(monkeypatch):
    import asyncio
    calls=iter([json.dumps({'tool':'overview'}),json.dumps({'claims':[{'text':'金额增加','citations':['DOES_NOT_EXIST']}]})])
    async def fake(messages):return next(calls)
    monkeypatch.setattr(services,'complete',fake)
    with pytest.raises(ValueError,match='校验'):asyncio.run(services.ask_ai('变化如何',analyse(Spec())))

def test_ai_rejects_free_numeric_claim(monkeypatch):
    import asyncio
    calls=iter([json.dumps({'tool':'overview'}),json.dumps({'claims':[{'text':'增长999%','citations':['E0117']}]})])
    async def fake(messages):return next(calls)
    monkeypatch.setattr(services,'complete',fake)
    with pytest.raises(ValueError,match='校验'):asyncio.run(services.ask_ai('变化如何',analyse(Spec())))

def test_real_extension_import_without_analysis_code_changes(monkeypatch,tmp_path):
    from backend import data
    content=(data.DATA/'wits-canada-cocoa.csv').read_bytes()
    monkeypatch.setattr(data,'DATA',tmp_path/'data/processed')
    monkeypatch.setattr(services,'DATA',tmp_path/'data/processed')
    monkeypatch.setattr(services,'ROOT',tmp_path)
    response=client.post('/api/import',files={'file':('canada.csv',content,'text/csv')},data={'name':'真实扩展验证','source_url':'https://wits.worldbank.org/'})
    assert response.status_code==200
    dataset_id=response.json()['dataset_id'];assert response.json()['records']==990
    for mode in ['competition','bilateral','comparison']:
        spec=Spec(dataset_id=dataset_id,mode=mode,reporter='CAN',reporters=['CAN'],partner='USA',products=['1806'])
        result=client.post('/api/analyse',json=spec.model_dump())
        assert result.status_code==200
        assert result.json()['classification']=='H0'

def test_saved_snapshot_does_not_follow_later_filter(monkeypatch,tmp_path):
    monkeypatch.setattr(services,'ROOT',tmp_path)
    first=client.post('/api/saved',json={'spec':Spec().model_dump(),'title':'快照'}).json()
    changed=client.post('/api/analyse',json=Spec(products=['0901']).model_dump()).json()
    saved=client.get('/api/saved/'+first['id']).json()
    assert saved['spec']['products']==['0902']
    assert saved['analysis_id']!=changed['analysis_id']

@pytest.mark.parametrize('malformed',[{'claims':['not-an-object']},{'claims':[{'text':'金额变化有差异','citations':['E0117']}],'limitations':{'bad':'shape'}}])
def test_ai_malformed_payload_rejected_before_ui(monkeypatch,malformed):
    import asyncio
    calls=iter([json.dumps({'tool':'overview'}),json.dumps(malformed)])
    async def fake(messages):return next(calls)
    monkeypatch.setattr(services,'complete',fake)
    with pytest.raises(ValueError):asyncio.run(services.ask_ai('分析变化',analyse(Spec())))

def test_same_scope_saves_distinct_records_and_notes(monkeypatch,tmp_path):
    monkeypatch.setattr(services,'ROOT',tmp_path)
    spec=Spec().model_dump()
    a=client.post('/api/saved',json={'spec':spec,'title':'第一份','note':'第一版笔记'}).json()
    b=client.post('/api/saved',json={'spec':spec,'title':'第二份','note':'第二版笔记'}).json()
    assert a['id']!=b['id'] and a['analysis_id']==b['analysis_id']
    assert client.get('/api/saved/'+a['id']).json()['saved_record']['note']=='第一版笔记'
    assert client.get('/api/saved/'+b['id']).json()['saved_record']['note']=='第二版笔记'

def test_legacy_sqlite_migration_preserves_saved_result(monkeypatch,tmp_path):
    import sqlite3
    monkeypatch.setattr(services,'ROOT',tmp_path)
    (tmp_path/'data').mkdir()
    with sqlite3.connect(tmp_path/'data/app.sqlite') as conn:
        conn.execute('CREATE TABLE analyses (id TEXT PRIMARY KEY,title TEXT,created TEXT,payload TEXT)')
        conn.execute('INSERT INTO analyses VALUES (?,?,?,?)',('legacy','旧分析','2026-10-18',json.dumps(analyse(Spec()))))
    saved=client.get('/api/saved/legacy').json()
    assert saved['saved_record']['title']=='旧分析' and saved['saved_record']['note']==''
    assert saved['summary']['current']>0

def test_export_notebook_escaped_and_tied_to_snapshot(monkeypatch,tmp_path):
    monkeypatch.setattr(services,'ROOT',tmp_path)
    body={'spec':Spec().model_dump(),'title':'我的报告 <script>','note':'第一行\n<script>不应执行</script>'}
    record=client.post('/api/saved',json=body).json()
    # Exporting an existing snapshot must not re-run analysis against a later dataset.
    import backend.app as app_module
    def fail_if_recomputed(*args,**kwargs):raise AssertionError('Saved report unexpectedly recomputed')
    monkeypatch.setattr(app_module,'analyse',fail_if_recomputed)
    response=client.post('/api/document/report',json=body|{'source_saved_id':record['id'],'expected_analysis_id':record['analysis_id']})
    assert response.status_code==200
    assert '研究笔记' in response.text and '&lt;script&gt;不应执行&lt;/script&gt;' in response.text
    assert '<script>' not in response.text
    assert '我的报告 &lt;script&gt;' in response.text

def test_document_rejects_changed_dataset_version():
    response=client.post('/api/document/report',json={'spec':Spec().model_dump(),'expected_analysis_id':'outdated-analysis'})
    assert response.status_code==422 and '已变化' in response.json()['detail']

def test_case_presets_are_real_runnable_scopes():
    cases=client.get('/api/cases').json()
    assert len(cases)==3
    for case in cases:
        result=client.post('/api/analyse',json=case['spec'])
        assert result.status_code==200
        if case['spec']['mode']!='comparison':assert result.json()['summary']['current']>0

def test_notebook_bundle_keeps_calculation_payload_clean():
    result=analyse(Spec());result['saved_record']={'title':'研究报告','note':'金额变化需复核'}
    with zipfile.ZipFile(io.BytesIO(services.export_zip(result))) as z:
        assert 'saved_record' not in json.loads(z.read('analysis.json'))
        assert json.loads(z.read('annotation.json'))['note']=='金额变化需复核'
        assert '研究笔记' in z.read('report.html').decode('utf-8')

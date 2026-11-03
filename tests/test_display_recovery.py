import importlib,json
from fastapi.testclient import TestClient
from backend.app import app


def test_application_shell_revalidates_after_a_fix():
    client=TestClient(app)
    for url in ['/','/index.html']:
        response=client.get(url)
        assert response.status_code==200
        assert response.headers['cache-control']=='no-store'
        assert 'translate="no"' in response.text


def test_client_diagnostics_are_bounded_and_redacted(monkeypatch,tmp_path):
    module=importlib.import_module('backend.app')
    monkeypatch.setattr(module,'ROOT',tmp_path)
    client=TestClient(app)
    fake_secret='sk-testcredentialforredaction123'
    payload={'kind':'chart','build':'test-build','message':'Canvas unavailable '+fake_secret,'stack':'test stack '+fake_secret,'component_stack':'Chart'}
    assert client.post('/api/client-errors',json=payload).status_code==200
    saved=json.loads((tmp_path/'output/client-errors.jsonl').read_text(encoding='utf-8'))
    assert fake_secret not in json.dumps(saved) and '[credential removed]' in saved['message']
    assert saved['created_at'] and saved['kind']=='chart'
    assert client.post('/api/client-errors',json=payload|{'message':'x'*1201}).status_code==422
    assert client.post('/api/client-errors',json=payload|{'settings':{}}).status_code==422

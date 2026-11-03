"""Verify all built-in combinations, then extract and run a real reproduction bundle."""
import hashlib, io, json, subprocess, sys, zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'.vendor'));sys.path.insert(0,str(ROOT))
from backend.analysis import Spec, analyse
from backend.data import get_dataset, catalogue
from backend.services import export_zip, export_diagnostic_zip, report
from backend.diagnostics import diagnose

def main():
    out=ROOT/'output/verification';out.mkdir(parents=True,exist_ok=True)
    rows,manifest,sha=get_dataset('wits-core');checks=[]
    for mode in ['competition','bilateral','comparison']:
        for reporter in ['USA','CHN','DEU','JPN','GBR']:
            for product in ['0901','0902','8703']:
                spec=Spec(mode=mode,reporter=reporter,partner='CHN' if reporter!='CHN' else 'USA',products=[product])
                result=analyse(spec,(rows,manifest,sha))
                if mode!='comparison':assert result['summary']['baseline'] is not None and result['summary']['current'] is not None
                for p in result['partners']:
                    if p.get('market_component') is not None:
                        assert abs(p['market_component']+p['share_component']-p['delta'])<=max(.001,abs(p['delta'])*1e-12)
                diagnostic=diagnose(result,injected=(rows,manifest,sha))
                assert diagnostic['analysis_id']==result['analysis_id'] and len(diagnostic['windows'])==4
                assert all(len(row['points'])==4 for row in diagnostic['rows'])
                assert len({e['id'] for e in diagnostic['evidence']})==len(diagnostic['evidence'])
                checks.append({'mode':mode,'reporter':reporter,'product':product,'status':'pass','diagnostic':'pass'})
    r=analyse(Spec());r['saved_record']={'title':'带笔记的复现验证报告','note':'开发复现验证：研究笔记应独立保存，不改变数值计算和证据。'};bundle=export_zip(r)
    (out/'trade-reproduction.zip').write_bytes(bundle);(out/'sample-report.html').write_text(report(r),encoding='utf-8')
    directory=out/('extracted-'+datetime.now().strftime('%Y%m%d%H%M%S'));directory.mkdir()
    with zipfile.ZipFile(io.BytesIO(bundle)) as z:
        for item in z.infolist():
            path=(directory/item.filename).resolve()
            assert path.is_relative_to(directory.resolve())
        z.extractall(directory)
        hashes=json.loads(z.read('checksums.json'))
        for name,digest in hashes.items():assert hashlib.sha256((directory/name).read_bytes()).hexdigest()==digest
    command=[sys.executable,'-X','utf8','-c',f"import sys,runpy;sys.path.insert(0,{str(ROOT/'.vendor')!r});runpy.run_path('reproduce.py',run_name='__main__')"]
    process=subprocess.run(command,cwd=directory,capture_output=True,text=True,encoding='utf-8',timeout=45)
    if process.returncode:raise RuntimeError(process.stdout+process.stderr)
    extension=analyse(Spec(dataset_id='wits-canada-cocoa',reporter='CAN',products=['1806']))
    assert extension['summary']['current'] is not None
    delivered=ROOT/'交付物/贸势有据-0.4.0-研究诊断复算包.zip'
    if not delivered.exists():
        delivered=out/'diagnostic-reproduction.zip'
        diagnostic_result=analyse(Spec(products=['8703']))
        delivered.write_bytes(export_diagnostic_zip(diagnostic_result,diagnose(diagnostic_result)))
    diag_directory=out/('diagnostic-extracted-'+datetime.now().strftime('%Y%m%d%H%M%S'));diag_directory.mkdir()
    with zipfile.ZipFile(delivered) as z:
        assert all((diag_directory/n).resolve().is_relative_to(diag_directory.resolve()) for n in z.namelist())
        z.extractall(diag_directory)
        for name,digest in json.loads(z.read('checksums.json')).items():assert hashlib.sha256((diag_directory/name).read_bytes()).hexdigest()==digest
    diag_command=[sys.executable,'-X','utf8','-c',f"import sys,runpy;sys.path.insert(0,{str(ROOT/'.vendor')!r});runpy.run_path('reproduce_diagnostic.py',run_name='__main__')"]
    diag_process=subprocess.run(diag_command,cwd=diag_directory,capture_output=True,text=True,encoding='utf-8',timeout=45)
    if diag_process.returncode:raise RuntimeError(diag_process.stdout+diag_process.stderr)
    summary={'created_at':datetime.now(timezone.utc).isoformat(),'combination_checks':checks,'reproduction':process.stdout.strip(),
        'bundle_sha256':hashlib.sha256(bundle).hexdigest(),'extension_records':catalogue('wits-canada-cocoa')['rows'],
        'diagnostic_reproduction':diag_process.stdout.strip(),'diagnostic_bundle_sha256':hashlib.sha256(delivered.read_bytes()).hexdigest(),
        'ai_live_test':'not_run_no_model_configured','real_user_test':'not_run'}
    (out/'verification.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'PASS: {len(checks)} analysis and diagnostic combinations; {process.stdout.strip()}; {diag_process.stdout.strip()}; real extension dataset; bundle checksums')

if __name__=='__main__':main()

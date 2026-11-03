"""Package source, built UI and retained data; exclude all credentials and runtime DBs."""
import hashlib, json, zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'交付物'; OUT.mkdir(exist_ok=True)
SKIP={'.vendor','node_modules','__pycache__','.pytest_cache','.playwright-cli','output','exports','交付物','.git'}
target=OUT/'贸势有据-0.5.3-源码与运行包.zip'
with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as z:
    files=[]
    for p in sorted(ROOT.rglob('*')):
        rel=p.relative_to(ROOT)
        if not p.is_file() or any(part in SKIP for part in rel.parts):continue
        if p.name.startswith('config.local') or p.suffix in {'.sqlite','.pyc','.tsbuildinfo'} or '.sqlite-' in p.name:continue
        if p.name.endswith('.log'):continue
        files.append((p,rel))
    hashes={}
    for path,rel in files:
        name=str(rel).replace('\\','/');raw=path.read_bytes();z.writestr(name,raw);hashes[name]=hashlib.sha256(raw).hexdigest()
    z.writestr('PACKAGE_CHECKSUMS.json',json.dumps(hashes,ensure_ascii=False,indent=2))
with zipfile.ZipFile(target) as z:
    assert z.testzip() is None
    assert not any('config.local' in n or 'app.sqlite' in n for n in z.namelist())
digest=hashlib.sha256(target.read_bytes()).hexdigest()
(OUT/'SHA256.txt').write_text(digest+'  '+target.name+'\n',encoding='utf-8')
print(json.dumps({'path':str(target),'files':len(files),'bytes':target.stat().st_size,'sha256':digest},ensure_ascii=False))

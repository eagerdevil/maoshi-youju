"""Bundle the frozen pilot and case with an actual four-window reproduction check."""
import hashlib,io,json,subprocess,sys,zipfile
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PILOT=ROOT/'evaluation/host-pilot-20261018'
OUTPUT=ROOT/'交付物/美国乘用车主案例与宿主AI预实验.zip'
SCRIPT='''from pathlib import Path
import hashlib,json,sys
root=Path(__file__).resolve().parent
if (root/'.vendor').exists():sys.path.insert(0,str(root/'.vendor'))
sys.path.insert(0,str(root))
from backend.analysis import Spec,analyse
pilot=root/'evaluation/host-pilot-20261018'
freeze=json.loads((pilot/'freeze.json').read_text(encoding='utf-8'))
for name,digest in freeze['files'].items():assert hashlib.sha256((pilot/name).read_bytes()).hexdigest()==digest
for key in ['main','window_2020','window_2021','window_2022']:
 old=json.loads((pilot/'inputs'/f'{key}.json').read_text(encoding='utf-8'))
 fresh=analyse(Spec(**old['spec']))
 assert fresh==old, key+' analysis changed'
 print('PASS:',key)
print('PASS: all four frozen analyses reproduced; model text not regenerated')
'''

def main():
    files={}
    for directory in [PILOT,ROOT/'研究成果/美国乘用车主案例']:
        for p in directory.rglob('*'):
            if p.is_file():files[str(p.relative_to(ROOT)).replace('\\','/')]=p.read_bytes()
    for name in ['backend/__init__.py','backend/analysis.py','backend/data.py','data/processed/wits-core.csv','data/processed/wits-core.manifest.json','scripts/check_host_pilot.py','scripts/build_main_case.py','scripts/audit_pilot_context.py']:
        files[name]=(ROOT/name).read_bytes()
    files['reproduce_case.py']=SCRIPT.encode('utf-8')
    files['requirements-reproduce.txt']=b'pydantic==2.14.1\n'
    readme='''主案例与宿主AI预实验资料包

先解压全部文件，再打开“研究成果/美国乘用车主案例/主案例分析报告.html”，可离线查看图表、来源和证据；同目录的AI预实验报告逐题保留首次回答与限制。

本次为同一宿主AI设计题、阅读参考值并作答的非盲开发预实验，没有普通AI基线和独立评分。12题完成、36项数值和26处引用通过机械校验，不等于模型准确率或优越性；应用内模型未连接。

冻结任务、参考值、4个分析窗口、源文件及指纹在evaluation/host-pilot-20261018。
使用Python先安装requirements-reproduce.txt，然后运行python reproduce_case.py，复算四个窗口。开发机已验证，计算不调用模型。
python scripts/check_host_pilot.py可复查冻结文件、引用和结构化数值；它不会自动评定语义。
重绘图表另需matplotlib及中文字体，预生成PNG/SVG无需安装即可使用。

context-audit记录当前应用只取前八伙伴和单窗口的证据缺口，不是模型运行成绩。新增指定伙伴查询、窗口比较及输出协议验证后，才适合做应用内端到端模型测试。
'''
    files['阅读说明.txt']=readme.encode('utf-8')
    hashes={name:hashlib.sha256(raw).hexdigest() for name,raw in files.items()}
    files['CHECKSUMS.json']=json.dumps(hashes,ensure_ascii=False,indent=2).encode('utf-8')
    with zipfile.ZipFile(OUTPUT,'w',zipfile.ZIP_DEFLATED) as z:
        for name,raw in files.items():z.writestr(name,raw)
    # Verify an extracted copy using the existing local dependency installation.
    directory=ROOT/'output/case-package-check'/datetime.now().strftime('%Y%m%d%H%M%S');directory.mkdir(parents=True)
    with zipfile.ZipFile(OUTPUT) as z:
        assert z.testzip() is None
        for item in z.infolist():assert (directory/item.filename).resolve().is_relative_to(directory.resolve())
        z.extractall(directory)
    for name,digest in hashes.items():assert hashlib.sha256((directory/name).read_bytes()).hexdigest()==digest
    code=f"import sys,runpy;sys.path.insert(0,{str(ROOT/'.vendor')!r});runpy.run_path('reproduce_case.py',run_name='__main__')"
    result=subprocess.run([sys.executable,'-X','utf8','-c',code],cwd=directory,text=True,capture_output=True,encoding='utf-8',timeout=40)
    if result.returncode:raise RuntimeError(result.stdout+result.stderr)
    digest=hashlib.sha256(OUTPUT.read_bytes()).hexdigest()
    verification={'verified_at':datetime.now(timezone.utc).isoformat(),'path':str(OUTPUT),'sha256':digest,'files':len(files),'reproduction':result.stdout.strip()}
    (PILOT/'delivery-check.json').write_text(json.dumps(verification,ensure_ascii=False,indent=2),encoding='utf-8')
    (OUTPUT.with_suffix('.sha256.txt')).write_text(digest+'  '+OUTPUT.name+'\n',encoding='utf-8')
    print(json.dumps(verification,ensure_ascii=False))

if __name__=='__main__':main()

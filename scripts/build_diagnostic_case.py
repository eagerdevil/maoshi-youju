"""Create a reviewable diagnostic example without modifying frozen pilot inputs."""
import hashlib
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'.vendor'))
sys.path.insert(0,str(ROOT))
from backend.analysis import Spec, analyse
from backend.diagnostics import diagnose, report
from backend.services import export_diagnostic_zip


def main():
    result=analyse(Spec(products=['8703']))
    diagnostic=diagnose(result)
    directory=ROOT/'研究成果/研究诊断示例'
    directory.mkdir(parents=True,exist_ok=True)
    artifacts={
        directory/'美国乘用车-跨基期研究诊断.html':report(diagnostic).encode('utf-8'),
        directory/'diagnostic.json':json.dumps(diagnostic,ensure_ascii=False,indent=2).encode('utf-8'),
        ROOT/'交付物/贸势有据-0.4.0-研究诊断复算包.zip':export_diagnostic_zip(result,diagnostic),
    }
    hashes={}
    for path,content in artifacts.items():
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(content)
        hashes[str(path.relative_to(ROOT)).replace('\\','/')]=hashlib.sha256(content).hexdigest()
    metadata={'analysis_id':result['analysis_id'],'diagnostic_id':diagnostic['diagnostic_id'],
              'windows':diagnostic['windows'],'counts':diagnostic['counts'],'sha256':hashes,
              'note':'确定性程序示例，不是AI模型回答或正式模型评测。方向计数可交叉，极小变化不按零处理。'}
    (directory/'artifacts.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(metadata,ensure_ascii=False))


if __name__=='__main__':main()

"""Audit information availability; not a model run or a task-accuracy measurement."""
import hashlib,json
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'evaluation/host-pilot-20261018'
r=json.loads((OUT/'inputs/main.json').read_text(encoding='utf-8'))
tasks=json.loads((OUT/'tasks.json').read_text(encoding='utf-8'))
focus=sorted(r['partners'],key=lambda p:abs(p['delta']) if p['delta'] is not None else -1,reverse=True)[:8]
ids={'main:'+p['evidence_id'] for p in focus}
ids.add('main:'+r['summary']['evidence_id'])
ids.update('main:'+r['structure'][key]['evidence_id'] for key in ['baseline','current'])
ids.add('main:'+r['structure']['residual_evidence_id'])
audit={'created_at':datetime.now(timezone.utc).isoformat(),'audit_type':'static_information_coverage_not_model_performance',
    'current_packet_partner_codes':[p['code'] for p in focus],
    'packet_rule':'Current backend/services.py selects eight partners by absolute amount delta, plus summary and structure.',
    'tasks':[{'id':t['id'],'missing_reference_citations':sorted(set(t['reference_citations'])-ids)} for t in tasks],
    'limitations':['无模型调用；缺少参考引用说明当前固定包不覆盖该任务所用证据，不等于模型实际回答错误。','宿主预实验读到完整结果和多个窗口，当前应用仅提供单窗口固定子集，二者信息条件不同。','宿主回答使用结构化数值清单，未执行API的claimsJSON与禁止自由数字协议。']}
directory=OUT/'context-audit';directory.mkdir(exist_ok=True)
source=(ROOT/'backend/services.py').read_bytes();(directory/'services.reviewed.py').write_bytes(source)
audit['services_sha256']=hashlib.sha256(source).hexdigest()
(directory/'audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'partners':audit['current_packet_partner_codes'],'tasks_missing_references':[x['id'] for x in audit['tasks'] if x['missing_reference_citations']]},ensure_ascii=False))

"""Freeze only the three previously exposed pilot tasks; never calls a model."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'evaluation/deepseek-20261019-v1'
OUT = ROOT / 'evaluation/deepseek-20261019-regression-v2'


def main():
    if OUT.exists():
        raise RuntimeError('Regression suite already exists; do not overwrite frozen files')
    latest = json.loads((SOURCE / 'latest-run.json').read_text(encoding='utf-8'))
    previous = json.loads((ROOT / latest['summary']).read_text(encoding='utf-8'))
    ids = list(dict.fromkeys(r['task_id'] for r in previous['results']))
    if len(ids) != 3:
        raise RuntimeError('Expected exactly three previously exposed tasks')
    all_tasks = json.loads((SOURCE / 'tasks.json').read_text(encoding='utf-8'))
    all_refs = json.loads((SOURCE / 'reference.json').read_text(encoding='utf-8'))
    selected = [next(t for t in all_tasks if t['id'] == key) for key in ids]
    protocol = json.loads((SOURCE / 'protocol.json').read_text(encoding='utf-8'))
    protocol.update({
        'title': 'DeepSeek修复后已见题回归-v2', 'tasks': 3,
        'evaluation_type': 'exposed_task_regression_not_independent_evaluation',
        'source_run': latest['summary'], 'task_ids': ids,
        'authorization': '仅复测先前已运行的三题，两流程，最多九次请求，不自动重试；剩余三十三题不调用。',
        'budget_limit_usd': 0.10,
        'price_note': '沿用2026-10-19原评测留存的Flash价格作估算，不是服务商账单保证。',
        'claim_limits': '这三题已用于发现问题和修改提示，只能评价开发回归；不得称为盲测、独立准确率或泛化表现。独立人工语义评价仍待完成。',
    })
    OUT.mkdir(parents=True)
    for name, value in [('tasks.json', selected), ('reference.json', {key: all_refs[key] for key in ids}), ('protocol.json', protocol)]:
        (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    relative_paths = [str((OUT / name).relative_to(ROOT)) for name in ['tasks.json', 'reference.json', 'protocol.json']]
    relative_paths += ['backend/services.py', 'backend/evidence_tools.py', 'backend/model_runtime.py',
                       'backend/analysis.py', 'backend/data.py', 'backend/__init__.py',
                       'data/processed/wits-core.csv', 'data/processed/wits-canada-cocoa.csv',
                       'scripts/run_model_evaluation.py', 'scripts/prepare_model_regression.py']
    hashes = {}
    for relative in relative_paths:
        relative = relative.replace('\\', '/')
        content = (ROOT / relative).read_bytes()
        hashes[relative] = hashlib.sha256(content).hexdigest()
        snapshot = OUT / 'frozen' / relative
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        snapshot.write_bytes(content)
    (OUT / 'freeze.json').write_text(json.dumps({'files': hashes, 'note': '运行前冻结；修改代码必须另建版本，旧输出不得覆盖。'}, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'suite': OUT.name, 'tasks': ids, 'frozen_files': len(hashes), 'live_requests': 0}, ensure_ascii=False))


if __name__ == '__main__':
    main()

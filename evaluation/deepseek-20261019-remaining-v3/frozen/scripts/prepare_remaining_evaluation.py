"""Freeze the 33 uncalled tasks without touching either previous evaluation."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'evaluation/deepseek-20261019-v1'
OUT = ROOT / 'evaluation/deepseek-20261019-remaining-v3'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def main():
    if OUT.exists():
        raise RuntimeError('Evaluation already exists; do not overwrite frozen files')
    original_freeze = read(SOURCE / 'freeze.json')['files']
    for filename in ['tasks.json', 'reference.json', 'protocol.json']:
        path = SOURCE / filename
        if hashlib.sha256(path.read_bytes()).hexdigest() != original_freeze[path.relative_to(ROOT).as_posix()]:
            raise RuntimeError('Original evaluation input changed')
    source_pointer = read(SOURCE / 'latest-run.json')
    prior = read(ROOT / source_pointer['summary'])
    exposed = {r['task_id'] for r in prior['results']}
    all_tasks = read(SOURCE / 'tasks.json')
    all_refs = read(SOURCE / 'reference.json')
    tasks = [t for t in all_tasks if t['id'] not in exposed]
    ids = {t['id'] for t in tasks}
    if len(exposed) != 3 or len(all_tasks) != 36 or len(tasks) != 33 or len(ids) != 33:
        raise RuntimeError('Expected precisely the remaining 33 original tasks')
    if ids & exposed or ids | exposed != {t['id'] for t in all_tasks}:
        raise RuntimeError('Task partition is invalid')
    protocol = read(SOURCE / 'protocol.json')
    protocol.update({
        'title': 'DeepSeek剩余三十三题首次运行-v3',
        'tasks': 33,
        'evaluation_type': 'remaining_tasks_first_run_same_task_family_not_blind',
        'source_run': source_pointer['summary'],
        'excluded_exposed_task_ids': sorted(exposed),
        'authorization': '用户明确要求把其余题目全都测试；仅剩余33题，两流程，最多99次请求，不自动重试。',
        'budget_limit_usd': 2.0,
        'price_note': '沿用2026-10-19留存的Flash公布价保守估算，不计缓存优惠，不是服务商账单保证。',
        'claim_limits': '这是其余题目的首次真实运行；题目与原三题共享模板，作者已编写和查看参考，不能称为独立盲测。数值命中由程序绑定，不是模型算术准确率；独立语义评价保持待完成。',
    })
    OUT.mkdir(parents=True)
    for name, value in [('tasks.json', tasks), ('reference.json', {key: all_refs[key] for key in sorted(ids)}), ('protocol.json', protocol)]:
        (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    paths = [str((OUT / name).relative_to(ROOT)) for name in ['tasks.json', 'reference.json', 'protocol.json']]
    paths += ['backend/services.py', 'backend/evidence_tools.py', 'backend/model_runtime.py',
              'backend/analysis.py', 'backend/data.py', 'backend/__init__.py',
              'data/processed/wits-core.csv', 'data/processed/wits-canada-cocoa.csv',
              'scripts/run_model_evaluation.py', 'scripts/run_remaining_evaluation.py',
              'scripts/prepare_remaining_evaluation.py']
    hashes = {}
    for relative in paths:
        relative = relative.replace('\\', '/')
        raw = (ROOT / relative).read_bytes()
        hashes[relative] = hashlib.sha256(raw).hexdigest()
        snapshot = OUT / 'frozen' / relative
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        snapshot.write_bytes(raw)
    (OUT / 'freeze.json').write_text(json.dumps({'files': hashes, 'note': '首次调用前冻结；运行期间不修改提示、代码、题目和参考；保留全部失败。'}, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'suite': OUT.name, 'tasks': len(tasks), 'excluded': sorted(exposed), 'frozen_files': len(hashes), 'live_requests': 0}, ensure_ascii=False))


if __name__ == '__main__':
    main()

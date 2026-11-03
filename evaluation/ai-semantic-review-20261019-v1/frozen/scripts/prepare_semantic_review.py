"""Freeze anonymous inputs for 66 responses. Does not call a model."""
import hashlib
import json
from pathlib import Path
import random
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '.vendor'))
sys.path.insert(0, str(ROOT))
from backend.analysis import Spec, analyse
from backend.evidence_tools import ToolPlan, execute, model_scope
from semantic_review_common import PROMPT, CRITERIA

SOURCE = ROOT / 'evaluation/deepseek-20261019-remaining-v3'
OUT = ROOT / 'evaluation/ai-semantic-review-20261019-v1'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def main():
    if OUT.exists():
        raise RuntimeError('Review already prepared; frozen inputs must not be overwritten')
    seal = read(SOURCE / 'first-results-seal.json')
    for name, digest in seal['files'].items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest:
            raise RuntimeError('Source output seal mismatch')
    pointer = read(SOURCE / 'latest-run.json')
    run = ROOT / Path(pointer['summary']).parent
    tasks = {t['id']: t for t in read(SOURCE / 'tasks.json')}
    files = sorted(run.glob('*.first.json'))
    if len(files) != 66:
        raise RuntimeError('Expected all 66 first responses')
    random.Random(2026101902).shuffle(files)
    OUT.mkdir(parents=True)
    entries = []
    mapping = []
    for index, path in enumerate(files, 1):
        payload = read(path)
        task = tasks[payload['task_id']]
        review_id = f'R{index:03d}'
        mapping.append({'review_id': review_id, 'task_id': payload['task_id'], 'group': payload['group'],
                        'source_path': path.relative_to(ROOT).as_posix(), 'source_sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
        if payload['status'] == 'failed':
            entries.append({'review_id': review_id, 'availability': 'no_usable_answer', 'packet': None})
            continue
        result = analyse(Spec(**task['spec']))
        baseline = execute(result, ToolPlan(**task['baseline_plan']))
        evidence = {e['id']: e for e in baseline['evidence']}
        evidence.update({e['id']: e for e in payload['answer'].get('evidence', [])})
        compact = [{k: e[k] for k in ['id', 'label', 'formula', 'operands', 'result', 'unit', 'status', 'note'] if k in e} for e in evidence.values()]
        answer = payload['answer']
        candidate = {k: answer[k] for k in ['status', 'answer', 'claims', 'limitations'] if k in answer}
        packet = {'question': task['question'], 'scope': model_scope(task['spec']), 'country_names': result['names'],
                  'data_sha256': task['data_sha256'], 'candidate': candidate, 'evidence': compact}
        entries.append({'review_id': review_id, 'availability': 'reviewable', 'packet': packet})
    protocol = {'title': '同模型AI辅助语义评价，不是独立人工评价', 'source_run': pointer['summary'],
                'responses': 66, 'reviewable_responses': sum(e['availability'] == 'reviewable' for e in entries),
                'maximum_requests': 60, 'budget_limit_usd': 2.0, 'automatic_retries': 0,
                'human_semantic_reviews_completed': 0, 'criteria': CRITERIA,
                'prompt': PROMPT, 'design': '单份匿名回答单独新会话，不提供流程名、自动评分、开发者已知问题或历史聊天；评价模型仍为DeepSeek Flash，同模型偏差未消除，不称为独立盲评。',
                'aggregation': '任一维度fail则AI总体fail；无fail但有uncertain则uncertain；其余pass。协议失败原回答记no_usable_answer，不调用评价模型。评价模型协议失败单列，不冒充语义失败。',
                'reference_boundary': '证据字段供复核，不发送参考评分或预期状态；仍未经过独立人工语义评价。'}
    if protocol['reviewable_responses'] != 60:
        raise RuntimeError('Expected precisely 60 reviewable and six failed responses')
    for name, data in [('inputs.json', entries), ('private-mapping.json', mapping), ('protocol.json', protocol)]:
        (OUT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    files_to_freeze = [OUT / name for name in ['inputs.json', 'private-mapping.json', 'protocol.json']]
    files_to_freeze += [ROOT / name for name in ['scripts/semantic_review_common.py', 'scripts/prepare_semantic_review.py', 'scripts/run_semantic_review.py',
                       'backend/services.py', 'backend/model_runtime.py', 'backend/evidence_tools.py', 'backend/analysis.py', 'backend/data.py']]
    hashes = {}
    for path in files_to_freeze:
        name = path.relative_to(ROOT).as_posix()
        raw = path.read_bytes()
        hashes[name] = hashlib.sha256(raw).hexdigest()
        target = OUT / 'frozen' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
    (OUT / 'freeze.json').write_text(json.dumps({'files': hashes, 'note': '评价首次调用前冻结匿名输入、题目映射、评分标准、提示和代码；不覆盖来源首次回答。'}, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'responses': 66, 'reviewable': 60, 'no_usable_answer': 6, 'live_requests': 0}, ensure_ascii=False))


if __name__ == '__main__':
    main()

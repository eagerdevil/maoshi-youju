"""Offline audit, replay of failed responses, sealing and report; never calls API."""
import asyncio
from collections import Counter, defaultdict
from fractions import Fraction
import hashlib
import html
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '.vendor'))
sys.path.insert(0, str(ROOT))
from backend import services
from backend.analysis import Spec, analyse
from backend.evidence_tools import ToolPlan, execute

SUITE = ROOT / 'evaluation/deepseek-20261019-remaining-v3'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def save_once(path, obj):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(obj, stream, ensure_ascii=False, indent=2)


async def offline_failure_reason(task, payload):
    responses = iter([event['content'] for event in payload['trace'] if isinstance(event.get('content'), str)])
    async def replay_only(*args, **kwargs):
        return next(responses)
    class NoNetwork:
        def __init__(self, *args, **kwargs):
            raise RuntimeError('Network is forbidden during offline audit')
    original_complete, original_client = services.complete, services.httpx.AsyncClient
    services.complete, services.httpx.AsyncClient = replay_only, NoNetwork
    try:
        result = analyse(Spec(**task['spec']))
        if payload['group'] == 'pipeline':
            await services.ask_ai(task['question'], result, persist=False)
        else:
            await services.explain_packet(task['question'], execute(result, ToolPlan(**task['baseline_plan'])))
        return {'reproduced': False, 'note': 'Offline replay did not reproduce this failure; inspect network metadata.'}
    except Exception as exc:
        return {'reproduced': True, 'type': type(exc).__name__, 'message': str(exc)[:1800]}
    finally:
        services.complete, services.httpx.AsyncClient = original_complete, original_client


def main():
    pointer = read(SUITE / 'latest-run.json')
    summary = read(ROOT / pointer['summary'])
    if not summary.get('finished_at') or len(summary['results']) != 66 or summary['tasks_planned'] != 33:
        raise RuntimeError('Batch is incomplete; do not report a completed evaluation')
    for name, digest in read(SUITE / 'freeze.json')['files'].items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest:
            raise RuntimeError('Frozen evaluation input changed: ' + name)
    tasks = {t['id']: t for t in read(SUITE / 'tasks.json')}
    refs = read(SUITE / 'reference.json')
    run = ROOT / Path(pointer['summary']).parent
    paths = sorted(run.glob('*.first.json'))
    if len(paths) != 66 or summary['budget']['requests'] > 99:
        raise RuntimeError('Unexpected batch size')
    # Verify independent reference values exist and agree with the fixed evidence.
    reference_audit = []
    for task_id, task in tasks.items():
        packet = execute(analyse(Spec(**task['spec'])), ToolPlan(**task['baseline_plan']))
        registry = {e['id']: e for e in packet['evidence']}
        for item in refs[task_id]['required_numbers']:
            valid = False
            for cid in item.get('accepted_citations', [item['citation']]):
                evidence = registry.get(cid)
                if evidence is None:
                    continue
                field = item['field']
                value = evidence['result'] if field == 'result' else evidence['operands'].get(field)
                expected = item['expected_fraction']
                if expected is None:
                    valid = field in evidence['operands'] and value is None
                elif value is not None:
                    tolerance = Fraction('0.01') if field in {'base', 'end', 'x0', 'x1'} else Fraction('0.00000001')
                    valid = abs(Fraction(value) - Fraction(expected)) <= tolerance
                if valid:
                    break
            reference_audit.append({'task_id': task_id, 'citation': item['citation'], 'field': item['field'], 'reference_resolvable_and_matches': valid})
    counts = {}
    failures = []
    mismatches = []
    omitted_numbers = []
    categories = defaultdict(lambda: defaultdict(Counter))
    outputs = []
    for path in paths:
        payload = read(path)
        outputs.append((path, payload))
        task_id, group, status = payload['task_id'], payload['group'], payload['status']
        categories[tasks[task_id]['category']][group][status] += 1
        if status == 'failed':
            failures.append({'task_id': task_id, 'group': group, 'first_response': path.relative_to(ROOT).as_posix(),
                             'offline_replay': asyncio.run(offline_failure_reason(tasks[task_id], payload))})
        if group == 'pipeline' and not payload['clarification_status_matches']:
            mismatches.append({'task_id': task_id, 'expected_status': refs[task_id]['expected_status'], 'actual_status': status})
        missing = [item for item in payload['number_checks'] if not item['present_and_correct']]
        if missing:
            omitted_numbers.append({'task_id': task_id, 'group': group, 'status': status, 'items': missing})
    for group in summary['groups']:
        records = [payload for _, payload in outputs if payload['group'] == group]
        statuses = Counter(r['status'] for r in records)
        checks = [n for r in records for n in r['number_checks']]
        counts[group] = {'attempts': len(records), 'statuses': dict(statuses),
                         'required_numeric_items': len(checks),
                         'numeric_items_present_and_correct': sum(n['present_and_correct'] for n in checks),
                         'pipeline_expected_status_matches': sum(r['clarification_status_matches'] is True for r in records) if group == 'pipeline' else None,
                         'independent_semantic_reviews_completed': 0}
    audit = {'run_id': summary['run_id'], 'counts': counts, 'categories': categories,
             'reference_audit': reference_audit, 'failures': failures, 'pipeline_status_mismatches': mismatches,
             'missing_required_numbers': omitted_numbers, 'review_type': 'automated_and_developer_audit_not_independent_human_review',
             'live_requests_during_report': 0}
    save_once(SUITE / 'offline-audit.json', audit)
    key_path = ROOT / 'config.local.json'
    key = read(key_path).get('api_key', '') if key_path.exists() else ''
    sealed = paths + [run / 'summary.json', SUITE / 'freeze.json', SUITE / 'offline-audit.json']
    hashes = {}
    for path in sealed:
        raw = path.read_bytes()
        if key and key.encode() in raw:
            raise RuntimeError('Credential detected; stop delivery')
        hashes[path.relative_to(ROOT).as_posix()] = hashlib.sha256(raw).hexdigest()
    save_once(SUITE / 'first-results-seal.json', {'run_id': summary['run_id'], 'files': hashes,
              'note': '运行后对首次输出与审计文件生成完整性封存，运行前冻结另见freeze.json。'})
    save_once(SUITE / 'independent-review-template.json', {
        'run_id': summary['run_id'], 'reviewer_alias': '', 'review_type': 'pending_independent_human_review',
        'instructions': '复制模板另存后填写；保留首次结果，开发者自查不计作独立评价。',
        'responses': [{'path': p.relative_to(ROOT).as_posix(), 'sha256': hashes[p.relative_to(ROOT).as_posix()],
                       'citation_support': None, 'role_correct': None, 'clarification_adequate': None,
                       'no_overclaim': None, 'wording_precise': None, 'notes': ''} for p in paths],
    })
    lines = ['# 剩余三十三题真实模型测试报告', '', f"运行ID：`{summary['run_id']}`。", '',
             '对原36题中此前未调用的33题，分别运行自动规划与固定证据流程；66份首次结果全部保留，无自动重试。原三题不重复调用。', '',
             f"本批实际API请求：**{summary['budget']['requests']}次**；按留存公布价、不计缓存优惠估算 **{summary['budget']['estimated_usd']:.6f}美元**，不是服务商账单金额保证。", '',
             '| 流程 | 正常回答 | 澄清 | 失败 | 要求数值匹配 |', '| --- | --- | --- | --- | --- |']
    for group, name in [('pipeline', '自动规划'), ('fixed_evidence', '固定证据')]:
        c = counts[group]
        s = c['statuses']
        lines.append(f"| {name} | {s.get('answered',0)} | {s.get('clarification',0)} | {s.get('failed',0)} | {c['numeric_items_present_and_correct']}/{c['required_numeric_items']} |")
    good = counts['pipeline']['pipeline_expected_status_matches']
    lines += ['', f'自动规划的预期状态匹配：{good}/33。越界年份题预期澄清，因此“全部answered”不是本测试的目标。固定证据流程跳过规划，不直接与澄清状态作同口径比较。', '',
              '数值匹配指要求的证据字段存在且与独立Fraction参考一致，程序负责绑定数值，不代表模型自行算术准确率。没有数值要求的题不进入该分母。', '',
              '## 按题型的协议状态', '', '| 题型 | 自动规划：回答/澄清/失败 | 固定证据：回答/澄清/失败 |', '| --- | --- | --- |']
    names = {'numeric': '金额与增长率', 'windows': '多时间窗口', 'role': '国家角色与流向', 'causal': '因果边界', 'scope': '越界年份', 'injection': '错误指令注入'}
    for category in sorted(categories):
        cells = []
        for group in ['pipeline', 'fixed_evidence']:
            s = categories[category][group]
            cells.append('/'.join(str(s.get(k, 0)) for k in ['answered', 'clarification', 'failed']))
        lines.append(f'| {names[category]} | {cells[0]} | {cells[1]} |')
    lines += ['', '## 失败的离线复现', '', '下列原因通过已保存的模型响应离线重放确定，没有再次调用模型，也没有改写首次结果。', '']
    for failure in failures:
        replay = failure['offline_replay']
        lines.append(f"- `{failure['task_id']} / {failure['group']}`：{replay.get('message', replay.get('note', '待核查'))}")
    if not failures:
        lines.append('- 本批没有协议失败。')
    lines += ['', '## 自动规划与预期状态不一致', '']
    for item in mismatches:
        lines.append(f"- `{item['task_id']}`：预期{item['expected_status']}，实际{item['actual_status']}。")
    if not mismatches:
        lines.append('- 本批未出现状态不匹配。')
    lines += ['', '## 要求数值未覆盖的题目', '']
    for item in omitted_numbers:
        lines.append(f"- `{item['task_id']} / {item['group']}`：状态{item['status']}，未命中{len(item['items'])}项；详见offline-audit.json。")
    if not omitted_numbers:
        lines.append('- 所有要求数值均已覆盖。')
    invalid_refs = [r for r in reference_audit if not r['reference_resolvable_and_matches']]
    lines += ['', '## 参考与适用边界', '',
              f'对全部要求数值做固定证据字段复核：共{len(reference_audit)}项，未能解析或不匹配{len(invalid_refs)}项。详细记录独立保存，不因结果不佳改写原参考。', '',
              '这是其余题目的首次真实运行，但题目与开发回归题共享模板，作者已编写并查看参考，不能称为独立盲测，也不能据此证明优于通用AI。', '',
              '**独立人工语义评价仍为零。**有效引用和数值绑定不能保证正文角色、因果和解释均正确。66份回答及待填独立评价模板已保留。', '',
              '原3题首轮、3题修复后回归、本批33题分批记录。三批不能混称为同一次36题首次评测。原PDF核验稿为历史版本，提交前仍需更新。', '',
              '## 记录位置', '',
              '- evaluation/deepseek-20261019-remaining-v3/freeze.json：运行前题目、参考及代码哈希；frozen目录保留原件。',
              '- runs目录：66份首次回答，含原始请求、响应、耗时及用量，不含密钥。',
              '- offline-audit.json：分类统计、参考字段复核、失败离线重放和未命中项。',
              '- first-results-seal.json：运行后输出完整性封存。',
              '- independent-review-template.json：独立人工评价待填写。', '']
    report = ROOT / '研究成果/真实模型试运行'
    report.mkdir(parents=True, exist_ok=True)
    (report / '剩余三十三题测试报告.md').write_text('\n'.join(lines), encoding='utf-8')
    page = '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>剩余三十三题真实测试</title><style>body{max-width:1100px;margin:30px auto;padding:20px;font:16px/1.8 system-ui;color:#264536}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f4f6f0;padding:18px}details{border-top:1px solid #ccc;padding:12px 0}</style>'
    page += '<pre>' + html.escape('\n'.join(lines)) + '</pre><h2>66份首次回答及失败记录</h2>'
    for path, payload in outputs:
        answer = payload['answer']
        display = {'status': payload['status'], 'error': payload['error'], 'question': tasks[payload['task_id']]['question'],
                   'claims': answer.get('claims'), 'limitations': answer.get('limitations'),
                   'clarification': answer.get('answer', answer.get('message', answer.get('clarification'))), 'tool_calls': answer.get('tool_calls'),
                   'number_checks': payload['number_checks']}
        if payload['status'] == 'failed':
            display['raw_response'] = [event.get('content') for event in payload['trace']]
        page += '<details><summary>' + html.escape(path.name + ' — ' + payload['status']) + '</summary><pre>'
        page += html.escape(json.dumps(display, ensure_ascii=False, indent=2)) + '</pre></details>'
    (report / '剩余三十三题测试报告.html').write_text(page + '</html>', encoding='utf-8')
    print(json.dumps({'counts': counts, 'failures': len(failures), 'reference_audit_items': len(reference_audit), 'invalid_reference_items': len(invalid_refs),
                      'requests': summary['budget']['requests'], 'estimated_usd': summary['budget']['estimated_usd'], 'report': str(report / '剩余三十三题测试报告.md')}, ensure_ascii=False))


if __name__ == '__main__':
    main()

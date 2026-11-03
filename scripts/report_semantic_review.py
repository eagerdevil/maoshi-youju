"""Offline report for the frozen AI-assisted review, with human review pending."""
from collections import Counter, defaultdict
import hashlib
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUITE = ROOT / 'evaluation/ai-semantic-review-20261019-v1'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def save_once(path, obj):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(obj, stream, ensure_ascii=False, indent=2)


def main():
    pointer = read(SUITE / 'latest-run.json')
    summary = read(ROOT / pointer['summary'])
    if not summary.get('finished_at') or len(summary['results']) != 66:
        raise RuntimeError('Incomplete review must not be reported as complete')
    for name, digest in read(SUITE / 'freeze.json')['files'].items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest:
            raise RuntimeError('Frozen review input changed: ' + name)
    protocol = read(SUITE / 'protocol.json')
    mapping = {e['review_id']: e for e in read(SUITE / 'private-mapping.json')}
    inputs = {e['review_id']: e for e in read(SUITE / 'inputs.json')}
    run = ROOT / Path(pointer['summary']).parent
    paths = sorted(run.glob('*.first.json'))
    results = [read(path) for path in paths]
    if len(results) != 66 or sum(len(r['trace']) for r in results) != summary['budget']['requests'] or summary['budget']['requests'] > 60:
        raise RuntimeError('Unexpected request count')
    groups = defaultdict(Counter)
    criteria = {name: Counter() for name in protocol['criteria']}
    findings, reviewer_failures, disagreements = [], [], []
    source_refs = read(ROOT / 'evaluation/deepseek-20261019-remaining-v3/reference.json')
    for result in results:
        meta = mapping[result['review_id']]
        verdict = result['evaluation']['overall'] if result['evaluation'] else result['status']
        groups[meta['group']][verdict] += 1
        if result['status'] == 'reviewer_failed':
            reviewer_failures.append({'review_id': result['review_id'], 'task_id': meta['task_id'], 'group': meta['group'], 'error': result['error']})
        if not result['evaluation']:
            continue
        if meta['group']=='pipeline' and meta['task_id'].endswith('-role') and result['evaluation']['criteria']['clarification_adequate']['rating']=='pass':
            candidate=inputs[result['review_id']]['packet']['candidate']
            if candidate.get('status')=='clarification':
                disagreements.append({'review_id':result['review_id'],'task_id':meta['task_id'],'group':meta['group'],
                    'kind':'unnecessary_clarification_accepted','developer_observation':'原问题要求解释已有国家角色，不需要新增伙伴条件；候选回答仍要求澄清。AI将澄清恰当性判通过，理由与明确评分标准存在分歧。',
                    'candidate':candidate,'ai_criterion':result['evaluation']['criteria']['clarification_adequate']})
        source=read(ROOT/meta['source_path'])
        missing=[item for item in source['number_checks'] if not item['present_and_correct']]
        if source['status']=='answered' and missing and result['evaluation']['criteria']['completeness']['rating']=='pass':
            disagreements.append({'review_id':result['review_id'],'task_id':meta['task_id'],'group':meta['group'],
                'kind':'missing_coverage_accepted','developer_observation':'已接受回答未覆盖题目要求的全部数值项，但AI将完整性判通过。按原要求字段复核漏项，不覆盖模型评分。',
                'missing_required_items':missing,'ai_criterion':result['evaluation']['criteria']['completeness']})
        for name, item in result['evaluation']['criteria'].items():
            criteria[name][item['rating']] += 1
            if item['rating'] in {'fail', 'uncertain'}:
                findings.append({'review_id': result['review_id'], 'task_id': meta['task_id'], 'group': meta['group'],
                                 'criterion': name, **item})
    analysis = {'run_id': summary['run_id'], 'review_type': 'same_model_ai_assisted_not_independent_human',
                'responses': 66, 'statuses': summary['statuses'], 'ai_verdicts': summary['ai_verdicts'],
                'groups': dict(groups), 'criteria': criteria, 'findings': findings, 'reviewer_failures': reviewer_failures,
                'developer_disagreements':disagreements,
                'human_semantic_reviews_completed': 0,
                'interpretation': 'AI通过只表示本次同模型审阅未标出问题；不等于人工确认、独立准确率或无错误。AI审阅会漏判和误判。原协议失败和评价协议失败均保留，不能删出总体分母。'}
    save_once(SUITE / 'review-analysis.json', analysis)
    key = read(ROOT / 'config.local.json').get('api_key', '') if (ROOT / 'config.local.json').exists() else ''
    hashes = {}
    for path in paths + [run / 'summary.json', SUITE / 'freeze.json', SUITE / 'review-analysis.json']:
        raw = path.read_bytes()
        if key and key.encode() in raw:
            raise RuntimeError('Credential detected; stop delivery')
        hashes[path.relative_to(ROOT).as_posix()] = hashlib.sha256(raw).hexdigest()
    save_once(SUITE / 'first-results-seal.json', {'run_id': summary['run_id'], 'files': hashes,
              'note': 'AI评价首次结果运行后封存；原回答及原独立人工评价模板保持不变。'})
    labels = {'citation_support': '引用支持', 'role_correct': '角色与流向', 'clarification_adequate': '澄清是否恰当',
              'no_overclaim': '解释边界', 'wording_precise': '表达精确', 'completeness': '回答完整性'}
    lines = ['# AI辅助语义评价报告', '',
             '**这是同模型AI辅助复核，不是独立人工评价。人工语义评价仍为待完成，完成数为零。**', '',
             f"评价运行ID：`{summary['run_id']}`。对剩余33题的两流程共66份首次结果做评价。", '',
             f"60份可审阅回答各最多调用一次；6份原始协议失败直接记为无可用回答，不调用评价模型。实际请求{summary['budget']['requests']}次，没有自动重试。", '',
             f"按留存价格、不计缓存优惠，估算本批费用{summary['budget']['estimated_usd']:.6f}美元；不是账单金额保证。", '',
             '## AI评价汇总', '',
             '| 原回答流程 | AI通过 | AI判不通过 | AI不确定 | 无可用回答 | 评价模型协议失败 |',
             '| --- | --- | --- | --- | --- | --- |']
    for group, label in [('pipeline', '自动规划'), ('fixed_evidence', '固定证据')]:
        s = groups[group]
        lines.append(f"| {label} | {s.get('pass',0)} | {s.get('fail',0)} | {s.get('uncertain',0)} | {s.get('no_usable_answer',0)} | {s.get('reviewer_failed',0)} |")
    lines += ['', 'AI总体判定规则：任一维度fail则总体不通过；无fail但有uncertain则不确定；其余为AI通过。无可用回答和评价协议失败单列，不能算通过或静默剔除。', '',
              '## 分维度统计', '', '| 维度 | AI通过 | AI判不通过 | AI不确定 | 不适用 |', '| --- | --- | --- | --- | --- |']
    for name in protocol['criteria']:
        s = criteria[name]
        lines.append(f"| {labels[name]} | {s.get('pass',0)} | {s.get('fail',0)} | {s.get('uncertain',0)} | {s.get('not_applicable',0)} |")
    lines += ['', '## 评价过程与局限', '',
              '- 评价前冻结评分标准、提示、匿名输入、随机顺序、回答映射和代码。各回答使用独立新会话，未向模型提供流程名、自动评分或开发者问题清单。',
              '- 每次评价均附原问题、有效国家角色、候选回答和证据字段；原始失败不拿未经校验的生成文字冒充有效回答。',
              '- 原回答与评价仍使用DeepSeek Flash。同模型偏差、提示偏差、盲化不完全均未消除；部分状态和回答风格本身可能暴露流程信息。',
              '- 本次匿名化只是减少标签干扰，不能称为独立盲评。题目和标准由开发者准备，也不是独立专家标准。',
              '- 评分输出只能引用已提供证据，协议错误保留。引用存在不等于评价理由正确，AI给出的负面或正面评价都需要人工复核。',
              '- 未修改原回答、原评测分数和独立人工评价模板。本报告不能用于将人工评价状态改成完成。', '',
              '## AI标记的问题与不确定项（待人工核查）', '']
    if not findings:
        lines.append('本次AI未标出问题；这不证明回答没有问题。')
    for item in findings:
        lines.append(f"- `{item['review_id']} / {item['task_id']} / {item['group']}`，{labels[item['criterion']]}（{item['rating']}）：{item['reason']}")
    lines += ['', '## 评价模型失败', '']
    for item in reviewer_failures:
        lines.append(f"- `{item['review_id']}`：{item['error']}。首次输出保留，未重试。")
    if not reviewer_failures:
        lines.append('评价协议均通过；不代表评价结论正确。')
    lines += ['', '## 开发者核查发现的评价分歧（非独立人工评价）', '',
              f'已记录{len(disagreements)}份回答的具体分歧。以下不修改AI首次评分，也不计入独立人工评价；用于说明同模型辅助评价存在漏判，AI通过数不能作为语义准确率。', '']
    for item in disagreements:
        lines.append(f"- `{item['review_id']} / {item['task_id']} / {item['group']}`：{item['developer_observation']} AI理由：{item['ai_criterion']['reason']}")
    lines += ['', '## 人工评价下一步', '',
              '请未参与开发的审阅者复制原independent-review-template.json另存，查看原问题、回答和证据，逐项填写。建议先独立评分，再对照AI意见，避免锚定。意见分歧单独记录，不覆盖首次评分。', '',
              '## 核验文件', '',
              '- evaluation/ai-semantic-review-20261019-v1/protocol.json：评价标准和限制。',
              '- inputs.json与private-mapping.json：冻结匿名输入及本地映射；映射不进入模型请求。',
              '- runs目录：66条评价记录，其中60条最多一次真实请求；记录原始请求、响应、耗时和用量。',
              '- review-analysis.json：逐项统计与问题清单；first-results-seal.json：输出完整性封存。', '']
    destination = ROOT / '研究成果/真实模型试运行'
    (destination / 'AI辅助语义评价报告.md').write_text('\n'.join(lines), encoding='utf-8')
    page = '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>AI辅助语义评价</title><style>body{max-width:1100px;margin:30px auto;padding:20px;font:16px/1.8 system-ui;color:#264536}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f4f6f0;padding:18px}details{border-top:1px solid #ccc;padding:12px 0}</style><pre>' + html.escape('\n'.join(lines)) + '</pre><h2>逐份回答与AI评价</h2>'
    for result in results:
        rid = result['review_id']
        packet = inputs[rid]['packet']
        display = {'mapping': mapping[rid], 'question': packet['question'] if packet else None,
                   'candidate': packet['candidate'] if packet else None, 'status': result['status'],
                   'evaluation': result['evaluation'], 'error': result['error']}
        page += '<details><summary>' + html.escape(rid + ' — ' + (result['evaluation']['overall'] if result['evaluation'] else result['status'])) + '</summary><pre>'
        page += html.escape(json.dumps(display, ensure_ascii=False, indent=2)) + '</pre></details>'
    (destination / 'AI辅助语义评价报告.html').write_text(page + '</html>', encoding='utf-8')
    print(json.dumps({'groups': dict(groups), 'statuses': summary['statuses'], 'ai_verdicts': summary['ai_verdicts'],
                      'flagged_criterion_items': len(findings), 'developer_disagreements':len(disagreements),'requests': summary['budget']['requests'],
                      'estimated_usd': summary['budget']['estimated_usd'], 'human_reviews': 0}, ensure_ascii=False))


if __name__ == '__main__':
    main()

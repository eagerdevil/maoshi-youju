"""Seal and report the completed 0.5.3 targeted run without more model calls."""
from collections import defaultdict,Counter
import hashlib
import html
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SUITE=ROOT/'evaluation/deepseek-20261019-targeted-v4'


def read(path):return json.loads(path.read_text(encoding='utf-8'))


def save_once(path,value):
    with path.open('x',encoding='utf-8') as stream:json.dump(value,stream,ensure_ascii=False,indent=2)


def main():
    pointer=read(SUITE/'latest-run.json');summary=read(ROOT/pointer['summary'])
    if not summary.get('finished_at') or len(summary['results'])!=13:raise RuntimeError('Incomplete retest')
    for name,digest in read(SUITE/'freeze.json')['files'].items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=digest:raise RuntimeError('Frozen retest changed: '+name)
    cases={c['case_id']:c for c in read(SUITE/'cases.json')}
    run=ROOT/Path(pointer['summary']).parent;paths=sorted(run.glob('*.first.json'));payloads=[read(p) for p in paths]
    if len(payloads)!=13 or sum(len(p['trace']) for p in payloads)!=summary['budget']['requests'] or summary['budget']['requests']>11:
        raise RuntimeError('Unexpected number of outputs or requests')
    for case in cases.values():
        if hashlib.sha256((ROOT/case['source_first_result']).read_bytes()).hexdigest()!=case['source_sha256']:
            raise RuntimeError('Original first response changed')
    groups=defaultdict(Counter)
    for item in payloads:
        g=groups[item['category']];g['cases']+=1;g['mechanical_pass']+=int(item['mechanical_pass']);g['requests']+=item['actual_api_requests']
    analysis={'run_id':summary['run_id'],'app_version':'0.5.3','categories':dict(groups),'totals':summary['totals'],
        'semantic_review':'pending','independent_human_reviews_completed':0,
        'note':'定向已见问题回归；6份规则答复不属于模型成功，数值命中与覆盖不代表自然语言正确。'}
    save_once(SUITE/'retest-analysis.json',analysis)
    key=read(ROOT/'config.local.json').get('api_key','') if (ROOT/'config.local.json').exists() else ''
    hashes={}
    for path in paths+[run/'summary.json',SUITE/'freeze.json',SUITE/'retest-analysis.json']:
        raw=path.read_bytes()
        if key and key.encode() in raw:raise RuntimeError('Credential detected; stop delivery')
        hashes[path.relative_to(ROOT).as_posix()]=hashlib.sha256(raw).hexdigest()
    save_once(SUITE/'first-results-seal.json',{'run_id':summary['run_id'],'files':hashes,'note':'运行后完整性封存；首次调用前冻结另见freeze.json。旧首次结果不覆盖。'})
    save_once(SUITE/'independent-review-template.json',{'run_id':summary['run_id'],'reviewer_alias':'','review_type':'pending_independent_human_review',
        'instructions':'复制模板另存后逐份填写；规则输出与模型输出分开，开发者自查不计作独立人工评价。',
        'responses':[{'path':p.relative_to(ROOT).as_posix(),'sha256':hashes[p.relative_to(ROOT).as_posix()],
            'citation_support':None,'role_correct':None,'clarification_adequate':None,'no_overclaim':None,'wording_precise':None,'completeness':None,'notes':''} for p in paths]})
    labels={'scope_rules':'当前角色说明（规则）','bilateral_pipeline':'双边规划与解释（模型）','numeric_fields':'引用字段（模型）','multi_country_windows':'多国多窗口（模型）'}
    totals=summary['totals']
    lines=['# 0.5.3针对性真实复测报告','',f"运行ID：`{summary['run_id']}`。本批验证13份已见问题结果，首次输出保留，无自动重试。",'',
        f"规则答复{totals['rule_answers']}份，不调用模型；真实模型正常回答{totals['live_model_answers']}份。本批实际API请求{summary['budget']['requests']}次。",'',
        f"协议、要求数值与覆盖的机械检查通过{totals['mechanical_pass']}/{totals['cases']}；要求数值匹配{totals['numeric_items_present_and_correct']}/{totals['required_numeric_items']}。",'',
        f"按留存公布价、不计缓存优惠，估算费用{summary['budget']['estimated_usd']:.6f}美元，估算上限0.50美元，不是账单金额保证。",'',
        '**这是针对已见问题的开发复测，不是独立盲测或整体准确率；独立人工语义评价仍待完成。**','',
        '| 核查类别 | 份数 | 机械检查通过 | 实际API请求 |','| --- | --- | --- | --- |']
    for category in labels:
        g=groups[category];lines.append(f"| {labels[category]} | {g['cases']} | {g['mechanical_pass']} | {g['requests']} |")
    lines += ['','## 逐份对照','','| 原问题与流程 | 原状态 | 本次状态 | 要求数值匹配 | 模型解释覆盖 | API请求 |','| --- | --- | --- | --- | --- | --- |']
    for item in payloads:
        before=read(ROOT/cases[item['case_id']]['source_first_result'])
        checks=item['number_checks'];coverage=item['answer'].get('coverage')
        cover=f"{coverage['model_covered']}/{coverage['required']}" if coverage and coverage['required'] else '不适用'
        lines.append(f"| {item['case_id']} | {before['status']} | {item['status']} | {sum(n['present_and_correct'] for n in checks)}/{len(checks)} | {cover} | {item['actual_api_requests']} |")
    lines += ['','## 如何理解结果','',
        '- 角色说明现在由业务入口读取当前参数和证据，不再向模型请求澄清。这六份结果应算规则核查，不能计作DeepSeek成功回答。',
        '- 双边四题走当前自动规划与解释流程；记录模型原规划、服务端规范化以及实际调用。不同伙伴、目录和年份约束不放开。',
        '- 两份字段问题及一份多窗口问题沿用原固定证据计划，真实请求模型重新解释，最多各一次；不是重新生成整批题目的结果。',
        '- 要求数值的参考继承原独立Fraction计算，未发送给模型。当前服务端的要求字段清单供模型遵守结构，不等同于发送参考评分。',
        '- 机械检查要求状态为answered、要求数值匹配且服务端覆盖完整；不充分的回答不能静默算通过。无要求数值的题不进入数字分母。',
        '- 自然语言因果、口径和措辞仍可能有错误；本轮不追加AI评分，也不把开发者阅读称为独立语义评价。','',
        '## 失败与未完成项','']
    failures=[item for item in payloads if not item['mechanical_pass']]
    if failures:
        for item in failures:lines.append(f"- {item['case_id']}：{item['status']}；{item['error']}；覆盖{item['answer'].get('coverage')}。原结果保留，不自动重试。")
    else:lines.append('本批未发现协议、要求数值或覆盖检查失败；这不表示自然语言已获独立确认。')
    lines += ['','## 核验资料','',
        '- evaluation/deepseek-20261019-targeted-v4/cases.json、reference.json、protocol.json：冻结范围与评分方式。',
        '- freeze.json及frozen目录：本次实际执行前的代码、提示与数据指纹原件。',
        '- runs目录：13份首次结果、实际模型请求与响应、耗时和用量；不包含密钥。',
        '- first-results-seal.json：运行后结果完整性封存；independent-review-template.json：人工评价待填写。','']
    destination=ROOT/'研究成果/真实模型试运行'
    (destination/'0.5.3针对性复测报告.md').write_text('\n'.join(lines),encoding='utf-8')
    page='<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>0.5.3针对性复测</title><style>body{max-width:1100px;margin:30px auto;padding:20px;font:16px/1.8 system-ui;color:#264536}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f4f6f0;padding:18px}details{border-top:1px solid #ccc;padding:12px 0}</style><pre>'+html.escape('\n'.join(lines))+'</pre><h2>13份首次完整回答</h2>'
    for item in payloads:
        task=cases[item['case_id']]['task'];answer=item['answer']
        display={'question':task['question'],'scope':task['spec'],'status':item['status'],'error':item['error'],
            'origin':item['response_origin'],'claims':answer.get('claims'),'limitations':answer.get('limitations'),
            'coverage':answer.get('coverage'),'plan_adjustments':answer.get('plan_adjustments'),'field_normalizations':answer.get('field_normalizations'),
            'requests':item['actual_api_requests'],'number_checks':item['number_checks']}
        page+='<details><summary>'+html.escape(item['case_id']+' — '+item['status'])+'</summary><pre>'+html.escape(json.dumps(display,ensure_ascii=False,indent=2))+'</pre></details>'
    (destination/'0.5.3针对性复测报告.html').write_text(page+'</html>',encoding='utf-8')
    print(json.dumps({'categories':dict(groups),'totals':totals,'requests':summary['budget']['requests'],'estimated_usd':summary['budget']['estimated_usd'],'independent_human_reviews':0},ensure_ascii=False))


if __name__=='__main__':main()

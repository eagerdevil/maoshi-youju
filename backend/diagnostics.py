"""Evidence-backed sensitivity checks; descriptive, without statistical inference."""
from __future__ import annotations
import hashlib
import html
import json
from decimal import Decimal
from .analysis import Spec, analyse
from .data import DataError, get_dataset

VERSION = '1.0.0'
STATE_NAMES = {
    'reversal': '方向反转', 'positive': '所选窗口均上升', 'negative': '所选窗口均下降',
    'flat': '所选窗口均持平', 'with_flat': '方向相同但含持平', 'insufficient': '证据不足',
}
QUADRANT_NAMES = {'both_up': '金额与份额均上升', 'both_down': '金额与份额均下降',
                  'amount_up_share_down': '金额上升、份额下降', 'amount_down_share_up': '金额下降、份额上升',
                  'flat': '含持平', 'insufficient': '证据不足'}


def decimal(value):
    return None if value is None else Decimal(value)


def direction(values):
    valid = [decimal(v) for v in values if v is not None]
    if len(valid) >= 2 and min(valid) < 0 < max(valid): return 'reversal'
    if len(valid) != len(values) or len(valid) < 2: return 'insufficient'
    if all(v > 0 for v in valid): return 'positive'
    if all(v < 0 for v in valid): return 'negative'
    if all(v == 0 for v in valid): return 'flat'
    return 'with_flat'


def quadrant(amount, share):
    a, s = decimal(amount), decimal(share)
    if a is None or s is None: return 'insufficient'
    if a == 0 or s == 0: return 'flat'
    if a > 0: return 'both_up' if s > 0 else 'amount_up_share_down'
    return 'amount_down_share_up' if s > 0 else 'both_down'


def diagnose(result, base_years=None, injected=None):
    loaded = injected or get_dataset(result['spec']['dataset_id'])
    raw, _, sha = loaded
    if sha != result['data_sha256']: raise DataError('数据版本已变化，请重新分析后诊断')
    spec = result['spec']
    reporters = spec['reporters'] if spec['mode'] == 'comparison' else [spec['reporter']]
    available = sorted({r['year'] for r in raw if r['reporter'] in reporters and r['flow'] == spec['flow']
                        and r['product'] in spec['products'] and spec['base_year'] <= r['year'] < spec['end_year']
                        and (spec['mode'] != 'bilateral' or r['partner'] == spec['partner'])})
    # The current baseline remains inspectable even if its records are absent.
    available = sorted(set(available + [spec['base_year']]))
    # Always preserve the root baseline; cap imported long panels to six comparisons.
    defaults = sorted(set([spec['base_year']] + available[-5:]))
    years = defaults if base_years is None else sorted(base_years)
    if not years or len(years) > 6 or len(set(years)) != len(years):
        raise DataError('诊断须选择一至六个不重复的基期')
    if any(type(y) is not int or y not in available for y in years):
        raise DataError('诊断基期须位于当前分析区间及可选基期目录内')
    competition = spec['mode'] == 'competition'
    metric = 'share_change_pp' if competition else 'growth_percent'
    windows, evidence, entities = [], {}, {}
    # Include the current window for the amount/share check even if not selected for sensitivity.
    analyses = {}
    for year in sorted(set(years + [spec['base_year']])):
        s = Spec(**(spec | {'base_year': year}))
        r = result if year == spec['base_year'] else analyse(s, loaded)
        analyses[year] = r
        if year in years:
            windows.append({'base_year': year, 'end_year': spec['end_year'], 'analysis_id': r['analysis_id']})
        ev_index = {e['id']: e for e in r['evidence']}
        for p in r['comparisons'] or r['partners']:
            ev = ev_index[p['evidence_id']]
            ref = f'{r["analysis_id"]}:{ev["id"]}'
            evidence[ref] = ev | {'id': ref, 'local_id': ev['id'], 'analysis_id': r['analysis_id'], 'spec': r['spec']}
            point = {'base_year': year, 'end_year': spec['end_year'], 'analysis_id': r['analysis_id'],
                     'baseline': ev['operands'].get('x0' if competition else 'base'),
                     'current': ev['operands'].get('x1' if competition else 'end'),
                     'delta': ev['result'], 'metric': ev['operands'].get(metric), 'evidence_id': ref,
                     'quadrant': quadrant(ev['result'], ev['operands'].get('share_change_pp')) if competition else None}
            entities.setdefault(p['code'], {'code': p['code'], 'name': p['name'], 'by_year': {}})['by_year'][year] = point
    rows = []
    for code, entity in entities.items():
        points = [entity['by_year'].get(y, {'base_year': y, 'end_year': spec['end_year'],
                   'analysis_id': analyses[y]['analysis_id'], 'baseline': None, 'current': None,
                   'delta': None, 'metric': None, 'evidence_id': None, 'quadrant': 'insufficient' if competition else None}) for y in years]
        primary = entity['by_year'].get(spec['base_year'])
        state = direction([p['metric'] for p in points])
        observed = sum(p['metric'] is not None for p in points)
        rows.append({'code': code, 'name': entity['name'], 'points': points, 'primary': primary,
                     'direction': state, 'direction_label': STATE_NAMES[state], 'observed_windows': observed,
                     'complete': observed == len(years), 'amount_direction': direction([p['delta'] for p in points]),
                     'quadrant': primary['quadrant'] if primary else ('insufficient' if competition else None)})
    rows.sort(key=lambda row: (-(decimal(row['primary']['current']) if row['primary'] and row['primary']['current'] is not None else Decimal(-1)), row['code']))
    counts = {'entities': len(rows), 'reversal': sum(r['direction'] == 'reversal' for r in rows),
              'consistent': sum(r['direction'] in {'positive', 'negative', 'flat'} for r in rows),
              'incomplete': sum(not r['complete'] for r in rows),
              'divergent': sum(r['quadrant'] in {'amount_up_share_down', 'amount_down_share_up'} for r in rows)}
    identity = {'analysis_id': result['analysis_id'], 'years': years, 'version': VERSION}
    did = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()[:20]
    return {'diagnostic_id': did, 'version': VERSION, 'analysis_id': result['analysis_id'], 'spec': spec,
            'title': result['title'], 'product_label': result['product_label'], 'dataset_name': result['dataset_name'],
            'data_sha256': sha, 'metric': metric, 'metric_label': '份额变化' if competition else '区间增长率',
            'unit': '百分点' if competition else '%', 'available_years': available, 'base_years': years,
            'windows': windows, 'rows': rows, 'counts': counts, 'evidence': list(evidence.values()),
            'sources': result['sources'], 'notes': [
                '固定报告期，只改变基期；窗口可能重叠，不能视作独立样本或统计显著性检验。',
                '至少两个可计算窗口才判断方向；仅一个窗口时展示数值，但方向诊断为证据不足。',
                '方向依据发布精度下的原始计算值，不按界面四舍五入值判断；极小非零变化仍有方向。',
                '仅检查所选窗口；方向一致不证明结论在其他时期成立，也不证明因果或竞争力。',
                '缺失、基期为零导致增长率无定义、世界分母为零均保留为证据不足；不按零补齐。',
                '区间增长率未年化，长短窗口不宜直接据此比较增长速度。',
                '金额与份额对照使用当前分析基期；方向反转可以与窗口覆盖不足同时存在。']}


def report(diagnostic):
    e = html.escape
    d = diagnostic
    def fmt(v):
        if v is None: return '数据不足'
        value=Decimal(v)
        return f'{value:+.3E}' if value and abs(value)<Decimal('0.00005') else f'{value:+,.4f}'
    headers = ''.join(f'<th>{y}—{d["spec"]["end_year"]}</th>' for y in d['base_years'])
    rows = []
    for row in d['rows']:
        cells = ''.join(f'<td>{fmt(p["metric"])}'+(f' <a href="#{e(p["evidence_id"])}">证据</a>' if p['evidence_id'] else '')+'</td>' for p in row['points'])
        cross = f'<td>{e(QUADRANT_NAMES[row["quadrant"]])}</td>' if d['metric']=='share_change_pp' else ''
        rows.append(f'<tr><td>{e(row["name"])} ({e(row["code"])})</td>{cells}<td>{e(row["direction_label"])}</td><td>{row["observed_windows"]}/{len(d["base_years"])}</td>{cross}</tr>')
    evs = ''.join(f'<details id="{e(x["id"])}"><summary>{e(x["id"])} · {x["spec"]["base_year"]}—{x["spec"]["end_year"]} · {e(x["label"])}</summary><p>{e(x["formula"])}</p><pre>{e(json.dumps({k:x[k] for k in ["operands","result","unit","record_ids"]},ensure_ascii=False,indent=2))}</pre></details>' for x in d['evidence'])
    notes = ''.join(f'<li>{e(n)}</li>' for n in d['notes'])
    used = {r['source_id'] for x in d['evidence'] for r in x['records']}
    sources = ''.join(f'<li><a href="{e(s["url"],quote=True)}">{e(s["id"])}</a> · SHA256 {e(s["sha256"])}</li>' for s in d['sources'] if s['id'] in used)
    return f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="icon" href="data:,"><title>研究诊断 · {e(d['product_label'])}</title><style>
body{{font:15px/1.8 system-ui;color:#183b38;max-width:1200px;margin:40px auto;padding:0 24px}}table{{border-collapse:collapse;width:100%;white-space:nowrap}}td,th{{padding:10px;border-bottom:1px solid #dae4dd;text-align:left}}a{{color:#27796b}}small{{overflow-wrap:anywhere}}pre{{white-space:pre-wrap;overflow-wrap:anywhere}}details{{padding:12px;border-bottom:1px solid #ddd}}li{{overflow-wrap:anywhere}}@media print{{body{{margin:0}}}}
</style><h1>换一个基期，结论还成立吗？</h1><p>{e(d['title'])} · {e(d['product_label'])} · {e(d['dataset_name'])}</p><small>根分析 {e(d['analysis_id'])} · 诊断 {e(d['diagnostic_id'])} · 诊断算法 {VERSION}<br>数据 SHA256 {e(d['data_sha256'])}</small>
<p>对象 {d['counts']['entities']}；所选窗口方向反转 {d['counts']['reversal']}；所选窗口均同向或持平 {d['counts']['consistent']}；窗口覆盖不足 {d['counts']['incomplete']}。分类计数可以交叉，不相加为总数。</p>
<h2>{e(d['metric_label'])} / {e(d['unit'])}</h2><div style="overflow-x:auto"><table><thead><tr><th>对象</th>{headers}<th>方向诊断</th><th>可计算窗口</th>{'<th>当前分析窗口金额与份额</th>' if d['metric']=='share_change_pp' else ''}</tr></thead><tbody>{''.join(rows)}</tbody></table></div>
<h2>方法与解释边界</h2><ul>{notes}</ul><p>由确定性程序生成，未调用模型。数值为公开表发布精度下的计算值；本诊断不是预测或显著性检验。</p><h2>证据索引</h2>{evs}<h2>原始来源</h2><ul>{sources}</ul></html>'''

"""Bounded, read-only evidence retrieval. The calculation engine remains unchanged."""
from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from .analysis import Spec, analyse
from .data import DataError, get_dataset


class ToolPlan(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    tool: Literal['overview', 'contributions', 'structure', 'comparison', 'partner', 'window_compare', 'clarify'] = 'overview'
    partners: list[str] = Field(default_factory=list, max_length=6)
    base_years: list[int] = Field(default_factory=list, max_length=4)
    clarification: str = Field(default='', max_length=600)

def model_scope(spec):
    """Only active roles enter the model context; inactive UI defaults are not facts."""
    keys={'dataset_id','mode','products','base_year','end_year','flow'}
    keys.update({'reporters'} if spec['mode']=='comparison' else {'reporter','partner'} if spec['mode']=='bilateral' else {'reporter'})
    return {k:v for k,v in spec.items() if k in keys}


def directory(result, loaded=None):
    rows, _, _ = loaded or get_dataset(result['spec']['dataset_id'])
    s = result['spec']
    reporters = s['reporters'] if s['mode'] == 'comparison' else [s['reporter']]
    selected = [r for r in rows if r['reporter'] in reporters and r['product'] in s['products'] and r['flow'] == s['flow']]
    return {'partners': sorted({(r['partner'], r['partner_name']) for r in selected if r.get('partner_type') == 'country_or_area'}),
            'years': sorted({r['year'] for r in selected})}


def execute(result, plan: ToolPlan):
    if plan.tool == 'clarify':
        raise DataError('澄清请求不执行计算工具')
    loaded = get_dataset(result['spec']['dataset_id'])
    if loaded[2] != result['data_sha256']:
        raise DataError('数据版本已变化，请重新分析')
    available = directory(result, loaded)
    if len(set(plan.partners)) != len(plan.partners) or len(set(plan.base_years)) != len(plan.base_years):
        raise DataError('伙伴或时间窗口重复')
    if plan.partners and result['spec']['mode'] != 'competition':
        raise DataError('指定供应伙伴工具适用于目标市场模式')
    if any(p not in {code for code, _ in available['partners']} for p in plan.partners):
        raise DataError('指定伙伴不在当前国家、商品和流向的数据目录中')
    if plan.tool == 'partner' and not plan.partners:
        raise DataError('请指定查询伙伴')
    if plan.tool == 'window_compare' and not plan.base_years:
        raise DataError('请指定比较窗口的基期')
    if plan.base_years and plan.tool != 'window_compare':
        raise DataError('时间窗口参数仅用于窗口比较工具')
    years = plan.base_years or [result['spec']['base_year']]
    if any(y not in available['years'] or y >= result['spec']['end_year'] for y in years):
        raise DataError('基期须存在于数据目录且早于当前报告期')
    windows, registry = [], []
    for year in years:
        spec = Spec(**(result['spec'] | {'base_year': year}))
        r = result if spec.model_dump() == result['spec'] else analyse(spec, loaded)
        aid = r['analysis_id']
        focus = ([p for p in r['partners'] if p['code'] in plan.partners] if plan.partners else
                 sorted(r['partners'], key=lambda p: abs(p['delta']) if p['delta'] is not None else -1, reverse=True)[:8])
        ids = {p['evidence_id'] for p in focus + r['comparisons']}
        if r['summary']['evidence_id']: ids.add(r['summary']['evidence_id'])
        if r['structure']:
            ids.update([r['structure']['baseline']['evidence_id'], r['structure']['current']['evidence_id'], r['structure']['residual_evidence_id']])
        def qualify(value):
            if isinstance(value, dict): return {k: qualify(v) for k, v in value.items()}
            if isinstance(value, list): return [qualify(v) for v in value]
            return f'{aid}:{value}' if isinstance(value, str) and value in ids else value
        selected_evidence = [e | {'id': f'{aid}:{e["id"]}', 'local_id': e['id'], 'analysis_id': aid, 'spec': r['spec']} for e in r['evidence'] if e['id'] in ids]
        registry.extend(selected_evidence)
        windows.append(qualify({'analysis_id': aid, 'spec': r['spec'], 'summary': r['summary'], 'partners': focus,
                               'unavailable_partners': [p for p in plan.partners if p not in {x['code'] for x in focus}],
                               'comparisons': r['comparisons'], 'structure': r['structure'], 'warnings': r['warnings']}))
    return {'analysis_id': result['analysis_id'], 'data_sha256': result['data_sha256'], 'windows': windows,
            'evidence': registry, 'tool_calls': [plan.model_dump() | {'analysis_ids': [w['analysis_id'] for w in windows]}]}


def bind_numbers(requests, refs, registry):
    """Resolve numbers from evidence; the model may select a field, never supply a value."""
    if not isinstance(requests, list) or len(requests) > 12:
        raise DataError('模型数值引用格式无效')
    bound = []
    for item in requests:
        if not isinstance(item, dict) or set(item) != {'citation', 'field'}:
            raise DataError('数值须引用证据字段，禁止模型填写数值')
        citation, field = item['citation'], item['field']
        if not isinstance(citation, str) or citation not in refs or not isinstance(field, str):
            raise DataError('数值引用与论断引用不一致')
        e = registry[citation]
        if field == 'result': value, unit = e['result'], e['unit']
        elif field in e['operands']:
            value = e['operands'][field]
            unit = '%' if field == 'growth_percent' else '百分点' if field in {'share_change_pp', 'contribution_pp'} else '比例' if field in {'s0', 's1'} else 'USD'
        else: raise DataError('引用的数值字段不存在')
        bound.append({'citation': citation, 'field': field, 'value': value, 'unit': unit, 'label': e['label']})
    return bound

"""Deterministic scope, plan and coverage guards; never invent model statements."""
import re
from .data import DataError
from .evidence_tools import ToolPlan, bind_numbers


def mentioned_years(question):
    translated = question.translate(str.maketrans('〇零一二三四五六七八九', '00123456789'))
    return list(dict.fromkeys(int(y) for y in re.findall(r'(?<!\d)(?:19|20)\d{2}(?!\d)', translated)))


def is_scope_question(question, result):
    """Only current-scope metadata questions qualify; requests for new data do not."""
    if not re.search(r'当前|现有|所选|本次', question) or not re.search(r'报告国|伙伴角色|贸易流向|国家角色', question):
        return False
    if re.search(r'增长率|增幅|份额变化|分别以|不同基期|预测|未来|明年|去年|改为|换成|切换|比较|多少|具体金额', question):
        return False
    if re.search(r'与[^，。；?？]{1,16}(?:贸易|进口|出口)',question):
        return False
    spec = result['spec']
    if any(y not in {spec['base_year'], spec['end_year']} for y in mentioned_years(question)):
        return False
    active = set(spec['reporters'] if spec['mode'] == 'comparison' else [spec['reporter']] + ([spec['partner']] if spec['mode'] == 'bilateral' else []))
    for code, name in result['names'].items():
        if code not in active and code != 'WLD' and (re.search(r'(?<![A-Z])' + re.escape(code) + r'(?![A-Z])', question) or len(name) >= 2 and name in question):
            return False
    return True


def normalize_plan(plan, result, question):
    """Repair redundant current-partner parameters, never change to another country."""
    raw = plan.model_dump()
    data = dict(raw)
    spec = result['spec']
    changes = []
    if spec['mode'] == 'bilateral':
        if plan.partners and plan.partners != [spec['partner']]:
            raise DataError('双边伙伴已固定，不能自动改成其他伙伴；请先切换分析范围')
        if plan.partners:
            data['partners'] = []
            changes.append('双边伙伴沿用当前范围，移除重复的供应伙伴参数')
        if plan.tool == 'partner':
            data['tool'] = 'window_compare' if plan.base_years else 'overview'
            changes.append('双边查询使用当前双边总览或窗口工具')
    if re.search(r'不同基期|分别以|多窗口|多个窗口|两个窗口|各基期', question):
        segment = re.search(r'(?:分别以|以)([^。；?？]*?)为基期', question)
        years = mentioned_years(segment.group(1) if segment else question)
        if years:
            if len(years) > 4:
                raise DataError('一次最多比较四个基期，请缩小窗口范围')
            if data['tool'] != 'clarify' and (data['tool'] != 'window_compare' or data['base_years'] != years):
                data.update(tool='window_compare', base_years=years)
                changes.append('按问题中明确列出的基期补齐窗口；目录和年份仍由工具校验')
    normalized = ToolPlan(**data)
    return normalized, ([{'original': raw, 'effective': normalized.model_dump(), 'reasons': changes}] if changes else [])


def scope_answer(result, packet):
    s, names = result['spec'], result['names']
    direction = '进口' if s['flow'] == 'M' else '出口'
    if s['mode'] == 'comparison':
        countries = '、'.join(names.get(c, c) for c in s['reporters'])
        world_flow = '自世界进口' if s['flow']=='M' else '对世界出口'
        text = f'报告国为{countries}，分别记录各报告国{world_flow}的金额；世界是统计总额口径，不是某个选定的双边伙伴。各国报告值不能相加解释为全球总额。'
    elif s['mode'] == 'bilateral':
        partner = names.get(s['partner'],s['partner'])
        pair_flow = f'自{partner}进口' if s['flow']=='M' else f'向{partner}出口'
        text = f'报告国为{names.get(s["reporter"], s["reporter"])}，伙伴为{partner}，流向为{direction}。金额表示该报告国{pair_flow}的商品贸易额，不是该国对世界总额。'
    else:
        text = f'报告国为{names.get(s["reporter"], s["reporter"])}，流向为{direction}；伙伴是向该目标市场供应所选商品的国家或地区。世界行表示该市场自世界进口总额，已列示伙伴合计不能当作全球总额。'
    refs = [w['summary']['evidence_id'] for w in packet['windows'] if w['summary']['evidence_id']]
    if not refs:
        refs = [row['evidence_id'] for w in packet['windows'] for row in w['comparisons']]
    return {'status': 'answered', 'model': '当前范围规则核查（未调用模型）', 'provider': 'deterministic',
            'response_origin': 'scope_rules', 'analysis_id': result['analysis_id'],
            'claims': [{'text': text, 'citations': refs, 'numbers': []}],
            'limitations': ['统计金额沿用当前数据包的名义美元口径；计价方式以原始来源说明为准，不自行推定。',
                            '缺失不等于零，金额变化不能直接证明政策因果或竞争力变化。'],
            'windows': packet['windows'], 'evidence': packet['evidence'], 'tool_calls': packet['tool_calls'],
            'data_sha256': result['data_sha256'], 'validation': '国家角色由当前分析参数读取，金额含义由计算口径说明；本回答未调用大模型。'}


def required_numbers(question, packet):
    """Build requested numeric coverage from live evidence, never evaluation files."""
    growth = bool(re.search(r'增长率|增幅|增长了', question))
    share = bool(re.search(r'份额', question))
    share_levels = share and not re.search(r'份额变化|百分点',question) and bool(re.search(r'基期.*报告期|两期|分别多少',question))
    amount = bool(re.search(r'金额', question)) and bool(re.search(r'基期|报告期|分别|多少|数值|金额与|金额和', question))
    calls = packet['tool_calls']
    window_query = any(c['tool'] == 'window_compare' for c in calls)
    if not (growth or share or amount or window_query):
        return []
    registry = {e['id']: e for e in packet['evidence']}
    required = []
    for window in packet['windows']:
        mode = window['spec']['mode']
        rows = window['comparisons'] if mode == 'comparison' else []
        if mode == 'comparison':
            explicit = [r for r in rows if r['name'] in question or re.search(r'(?<![A-Z])' + re.escape(r['code']) + r'(?![A-Z])', question)]
            rows = explicit or rows
        elif mode == 'competition':
            partners = window['partners']
            explicit = [r for r in partners if r['name'] in question or re.search(r'(?<![A-Z])' + re.escape(r['code']) + r'(?![A-Z])', question)]
            selected = any(c.get('partners') for c in calls)
            rows = explicit or (partners if selected else [])
        if not rows:
            if not window['summary']['evidence_id']:
                continue
            rows = [{'evidence_id': window['summary']['evidence_id'], 'name': '当前范围总额'}]
        for row in rows:
            cid = row['evidence_id']
            evidence = registry[cid]
            fields = []
            if amount:
                fields += ['x0', 'x1'] if 'x0' in evidence['operands'] else ['base', 'end']
            if growth or window_query and not share:
                fields.append('growth_percent')
            if share:
                if 'share_change_pp' not in evidence['operands']:
                    raise DataError('当前模式没有可核查的市场份额字段，请切换目标市场模式或调整问题')
                fields.extend(['s0','s1'] if share_levels else ['share_change_pp'])
            for field in fields:
                if field not in evidence['operands']:
                    raise DataError('问题要求的数值字段不在当前证据中，请调整范围')
                key = (cid, field)
                if any((r['citation'], r['field']) == key for r in required):
                    continue
                bound = bind_numbers([{'citation': cid, 'field': field}], [cid], registry)[0]
                required.append(bound | {'object': row['name'], 'base_year': window['spec']['base_year'], 'end_year': window['spec']['end_year']})
    return required


def check_coverage(required, claims, registry=None):
    present = {(n['citation'], n['field']) for c in claims for n in c['numbers']}
    def covered(row):
        if (row['citation'], row['field']) in present:
            return True
        if not registry:
            return False
        target = registry[row['citation']]
        records = set(target.get('record_ids', []))
        if not records:
            return False
        # A single-product bilateral row and its total can represent the same observations.
        for claim in claims:
            for number in claim['numbers']:
                other = registry[number['citation']]
                if number['field']==row['field'] and number['value']==row['value'] and number['unit']==row['unit'] and other['analysis_id']==target['analysis_id'] and set(other.get('record_ids', []))==records:
                    return True
        return False
    rows = [r | {'covered_by_model': covered(r)} for r in required]
    missing = [r for r in rows if not r['covered_by_model']]
    return {'complete': not missing, 'required': len(rows), 'model_covered': len(rows) - len(missing),
            'rows': rows, 'missing': missing,
            'origin': 'deterministic_evidence_table_not_model_completion'}


def answer_presentation(question, claims, limitations, required, registry):
    """Select relevant claims for display, preserving every original statement."""
    warnings = []
    for section, texts in [('claims', [c['text'] for c in claims]), ('limitations', limitations)]:
        for index, text in enumerate(texts):
            # A narrow, high-confidence guard; this is not a general semantic grader.
            for sentence in re.split(r'[。；;！!？?]', text):
                if re.search(r'(?:增长|增幅|增长率|下降率|降幅)[^，,。；;]{0,24}个百分点', sentence) and not re.search(r'份额|占比|比重|利率|税率|增长率变化|增速变化|增长率之差', sentence):
                    warnings.append({'section': section, 'index': index,
                                     'message': '此处可能混用百分比与百分点，请以证据数值的单位为准；原文待复核。'})
                    break
    simple = bool(required) and bool(re.search(r'金额|增长率|增幅|份额', question)) and not re.search(r'原因|为何|为什么|解释|分解|贡献|政策|因果|建议|风险|结构|趋势|分析|证明|忽略|指令', question)
    primary = []
    if simple:
        # Keep every claim needed to cover requested numbers, including equivalent
        # bilateral evidence. Unrelated context is available in a disclosure.
        covered = set()
        for i, claim in enumerate(claims):
            rows = check_coverage(required, [claim], registry)['rows']
            keys = {j for j, row in enumerate(rows) if row['covered_by_model']}
            if keys - covered:
                primary.append(i)
                covered.update(keys)
    if not primary:
        primary = list(range(len(claims)))
    return {'primary_claim_indices': primary,
            'additional_claim_indices': [i for i in range(len(claims)) if i not in primary],
            'wording_warnings': warnings, 'original_text_preserved': True}

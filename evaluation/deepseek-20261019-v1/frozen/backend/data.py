from __future__ import annotations
import csv, hashlib, io, json, re
from decimal import Decimal, InvalidOperation
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data/processed'
REQUIRED = {'reporter','reporter_name','partner','partner_name','year','flow','product','product_name','classification','value_usd','status'}

class DataError(ValueError):
    pass

def load_rows(content: bytes, source_id: str = '') -> list[dict]:
    try:
        reader = csv.DictReader(io.StringIO(content.decode('utf-8-sig')))
        if not REQUIRED.issubset(reader.fieldnames or []):
            raise DataError('缺少字段：' + '、'.join(sorted(REQUIRED-set(reader.fieldnames or []))))
        rows=[]; keys=set(); ids=set()
        for line, raw in enumerate(reader, 2):
            r={k:(v or '').strip() for k,v in raw.items() if k is not None}
            if any(not r.get(k) for k in REQUIRED-{'value_usd'}):
                raise DataError(f'第{line}行必填字段为空')
            if r['flow'] not in {'M','X'} or r['status'] not in {'observed','explicit_zero','missing'}:
                raise DataError(f'第{line}行贸易流或观测状态不合法')
            if not re.fullmatch(r'[A-Z0-9_-]{2,16}', r['reporter']) or not re.fullmatch(r'[A-Z0-9_-]{2,16}',r['partner']):
                raise DataError(f'第{line}行国家代码不合法；世界使用WLD')
            if r['reporter']=='WLD': raise DataError('WLD不能作为本版报告国')
            r['partner_type']=r.get('partner_type') or ('world' if r['partner']=='WLD' else 'country_or_area')
            if r['partner_type'] not in {'world','country_or_area','aggregate','unallocated'}: raise DataError('伙伴实体类型不合法')
            if (r['partner']=='WLD') != (r['partner_type']=='world'): raise DataError('世界代码与实体类型不一致')
            if not re.fullmatch(r'\d{2}|\d{4}|\d{6}',r['product']):
                raise DataError(f'第{line}行商品编码必须为2/4/6位数字，保留前导零')
            if not re.fullmatch(r'H[0-6]',r['classification']):
                raise DataError(f'第{line}行分类版本必须明确为H0—H6')
            try:
                r['year']=int(r['year'])
                if not 1960<=r['year']<=2100: raise ValueError()
                value=None if r['status']=='missing' else Decimal(r['value_usd'])
                if value is not None and (not value.is_finite() or value<0): raise ValueError()
                if r['status']=='explicit_zero' and value!=0: raise ValueError()
                if r['status']=='missing' and r['value_usd']: raise ValueError()
            except (InvalidOperation,ValueError):
                raise DataError(f'第{line}行年份、美元金额或缺失标记不合法')
            key=tuple(r[k] for k in ['reporter','partner','year','flow','product','classification'])
            if key in keys: raise DataError(f'第{line}行重复主键；请先核对额外维度，禁止静默去重')
            keys.add(key)
            r['record_id']=r.get('record_id') or f'{source_id}:{line}'
            if r['record_id'] in ids: raise DataError(f'第{line}行记录ID重复')
            ids.add(r['record_id']); r['value']=value
            r['source_id']=r.get('source_id') or source_id
            r['source_row']=r.get('source_row') or line
            rows.append(r)
            if len(rows)>150000: raise DataError('单数据包最多150000条记录')
        if not rows: raise DataError('数据表没有记录')
        return rows
    except UnicodeDecodeError:
        raise DataError('请提供UTF-8编码CSV')

def datasets():
    DATA.mkdir(parents=True,exist_ok=True)
    result=[]
    for p in sorted(DATA.glob('*.manifest.json')):
        manifest=json.loads(p.read_text(encoding='utf-8'))
        if (DATA/f"{manifest['dataset_id']}.csv").exists():
            result.append(manifest)
    return result

def get_dataset(dataset_id):
    if not re.fullmatch(r'[a-zA-Z0-9_-]+',dataset_id): raise DataError('数据包ID不合法')
    path=DATA/f'{dataset_id}.csv'; mp=DATA/f'{dataset_id}.manifest.json'
    if not path.exists() or not mp.exists(): raise DataError('数据包不存在')
    content=path.read_bytes()
    return load_rows(content,dataset_id),json.loads(mp.read_text(encoding='utf-8')),hashlib.sha256(content).hexdigest()

def catalogue(dataset_id):
    rows,manifest,fingerprint=get_dataset(dataset_id)
    reporters={r['reporter']:r['reporter_name'] for r in rows}
    partners={r['partner']:r['partner_name'] for r in rows if r['partner_type']=='country_or_area'}
    products={r['product']:r['product_name'] for r in rows}
    coverage={}
    for r in rows:
        if r['partner']=='WLD' and r['value'] is not None:
            key=(r['reporter'],r['flow'],r['product'],r['classification'])
            coverage.setdefault(key,[]).append(r['year'])
    return {'id':dataset_id,'name':manifest['name'],'rows':len(rows),'sha256':fingerprint,
        'reporters':[{'code':k,'name':v} for k,v in reporters.items()],
        'partners':[{'code':k,'name':v} for k,v in partners.items() if k!='WLD'],
        'products':[{'code':k,'name':v} for k,v in products.items()],
        'years':sorted({r['year'] for r in rows}),
        'coverage':[{'reporter':k[0],'flow':k[1],'product':k[2],'classification':k[3],'years':sorted(set(v))} for k,v in coverage.items()],
        'manifest':manifest}

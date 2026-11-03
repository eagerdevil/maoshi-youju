"""Download official WITS public tables; raw HTML and source manifest are retained.
No invented observations, no replacing absent records with zero.
Run explicitly; the application never scrapes in the background.
"""
from __future__ import annotations
import argparse, csv, hashlib, json, re, sys, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
REPORTERS = {'USA':'美国', 'CHN':'中国', 'DEU':'德国', 'JPN':'日本', 'GBR':'英国', 'CAN':'加拿大'}
PRODUCTS = {'0901':'咖啡', '0902':'茶叶', '8703':'乘用车', '1806':'巧克力及其他含可可食品'}
PARTNER_LINK_FIXES = {"Cote d'Ivoire":'CIV', 'Saint Barthélemy':'BLM',
    'Saint Maarten (Dutch part)':'SXM', 'Bonaire':'BES'}

def fetch(task):
    reporter, year, flow, product = task
    key = f'{reporter}-{year}-{flow}-{product}'
    url = f'https://wits.worldbank.org/trade/comtrade/en/country/{reporter}/year/{year}/tradeflow/{flow}/partner/ALL/product/{product}'
    path = ROOT / 'data/raw' / f'{key}.html'
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raw = path.read_bytes()
    else:
        response = requests.get(url, timeout=55)
        response.raise_for_status()
        raw = response.content
        path.write_bytes(raw)
        time.sleep(.35)
    soup = BeautifulSoup(raw, 'html.parser')
    text = soup.get_text(' ', strip=True)
    classification = re.search(r'HS\s*(?:19|20)\d{2}(?:/\d{2})?\s*\((H\d)\)', text, re.I)
    # WITS trade/comtrade tables explicitly identify HS 1988/92 (H0).
    if not classification:
        classification = re.search(r'\b(H[0-6])\b', text)
    if not classification:
        raise ValueError(f'{key}: classification not documented on source page')
    klass = classification.group(1)
    rows = []
    for tr in soup.select('table tr'):
        cells = tr.find_all('td')
        if len(cells) < 8:
            continue
        values = [c.get_text(' ', strip=True) for c in cells]
        if values[2] != product or values[4] != str(year):
            continue
        anchor = cells[5].find('a', href=True)
        match = re.search(r'/partner/([^/\s?]+)', anchor['href']) if anchor else None
        if not match:
            # Some tables link partner profiles instead of the current table.
            match = re.search(r'/Country/([^/\s?]+)', anchor['href'], re.I) if anchor else None
        if values[5] == 'World':
            partner = 'WLD'
        elif values[5] in PARTNER_LINK_FIXES:
            partner = PARTNER_LINK_FIXES[values[5]]
        elif match:
            partner = match.group(1)
        else:
            raise ValueError(f'{key}: no partner code for {values[5]}')
        if partner == 'WLD' and values[5] != 'World':
            raise ValueError(f'{key}: source partner hyperlink points to World for {values[5]}')
        partner_source_code=partner
        partner_type='world' if partner=='WLD' else 'country_or_area'
        if partner=='UNS' or values[5] in {'Unspecified','Bunkers','Free Zones','Special Categories'}:
            # WITS can publish several indistinguishable 'Unspecified' rows. Preserve each
            # without inventing a cross-year partner identity or silently aggregating them.
            partner='UNK_'+hashlib.sha256(f'{key}:{len(rows)+1}'.encode()).hexdigest()[:10].upper()
            partner_type='unallocated'
        amount = Decimal(values[6].replace(',','')) * 1000
        rows.append({'record_id':f'{key}:{len(rows)+1}', 'reporter':reporter,
            'reporter_name':REPORTERS[reporter], 'partner':partner, 'partner_name':values[5],
            'year':year, 'flow':'M' if flow=='Imports' else 'X', 'product':product,
            'product_name':PRODUCTS[product], 'classification':klass, 'value_usd':str(amount),
            'status':'observed', 'source_id':key, 'source_row':len(rows)+1})
        rows[-1].update({'partner_source_code':partner_source_code,'partner_type':partner_type})
    if not rows or not any(r['partner']=='WLD' for r in rows):
        raise ValueError(f'{key}: no complete table or World denominator')
    return rows, {'id':key, 'url':url, 'raw_file':str(path.relative_to(ROOT)).replace('\\','/'),
        'sha256':hashlib.sha256(raw).hexdigest(), 'retrieved_at':datetime.now(timezone.utc).isoformat(),
        'rows':len(rows), 'classification':klass, 'unit':'USD',
        'original_unit':'1000 USD; displayed to 0.01 thousand USD',
        'note':'WITS public table, underlying UN Comtrade; rounded published values. No absent partner imputed as zero.'}

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--years',default='2019,2020,2021,2022,2023')
    parser.add_argument('--reporters',default='USA,CHN,DEU,JPN,GBR'); parser.add_argument('--products',default='0901,0902,8703')
    parser.add_argument('--dataset-id',default='wits-core'); parser.add_argument('--name',default='WITS 多国三行业贸易数据包')
    parser.add_argument('--workers',type=int,default=2); args=parser.parse_args()
    tasks=[(r,int(y),f,p) for r in args.reporters.split(',') for y in args.years.split(',') for f in ['Imports','Exports'] for p in args.products.split(',')]
    records=[]; sources=[]; errors=[]
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures={pool.submit(fetch,t):t for t in tasks}
        for future in as_completed(futures):
            task=futures[future]
            try:
                rows,source=future.result(); records.extend(rows); sources.append(source)
                print('OK',*task,len(rows),flush=True)
            except Exception as exc:
                errors.append({'task':task,'error':str(exc)}); print('FAIL',*task,str(exc),flush=True)
    records.sort(key=lambda r:(r['reporter'],r['year'],r['flow'],r['product'],r['partner']))
    target=ROOT/'data/processed'; target.mkdir(parents=True,exist_ok=True)
    if records:
        with (target/f'{args.dataset_id}.csv').open('w',encoding='utf-8-sig',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=list(records[0])); writer.writeheader(); writer.writerows(records)
    manifest={'dataset_id':args.dataset_id,'name':args.name,'source':'World Bank WITS / UN Comtrade',
        'collected_at':datetime.now(timezone.utc).isoformat(),'records':len(records),'sources':sorted(sources,key=lambda s:s['id']),
        'errors':errors,'scope':{'reporters':args.reporters.split(','),'years':args.years,'products':args.products.split(',')},
        'license_url':'https://wits.worldbank.org/terms-of-use.html',
        'partner_code_repairs':{'reason':'Four named partner hyperlinks incorrectly point to WLD in WITS HTML; corrected by partner name, not by hyperlink.',
            'mapping':PARTNER_LINK_FIXES,'reference_url':'https://comtradeapi.un.org/files/v1/app/reference/partnerAreas.json'},
        'unallocated_policy':'Unspecified rows are preserved with source-row identities; never interpreted as comparable countries across years.',
        'limitations':['发布表按千美元保留两位小数，计算存在展示精度边界。','未列示伙伴不等于零。','以页面注明的商品分类版本为准。','最新可用年份不等于完整年份；本包只代表已下载范围。']}
    (target/f'{args.dataset_id}.manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'records':len(records),'tables':len(sources),'failed':len(errors)},ensure_ascii=False),flush=True)
    return 0 if records else 1

if __name__=='__main__': sys.exit(main())

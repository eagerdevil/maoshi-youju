"""Small independent official-endpoint spot check. This is not a full audit."""
import csv, hashlib, json, time, sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
import requests

ROOT=Path(__file__).resolve().parents[1]
CASES=[('USA',842,2023,'M','0902','WLD',0),('USA',842,2019,'M','0902','WLD',0),
       ('USA',842,2023,'M','0902','CHN',156),('USA',842,2023,'M','0901','WLD',0),
       ('DEU',276,2023,'M','8703','WLD',0),('CHN',156,2023,'X','8703','WLD',0)]

def main():
    rows=list(csv.DictReader((ROOT/'data/processed/wits-core.csv').open(encoding='utf-8-sig')))
    directory=ROOT/'evaluation/source-check';directory.mkdir(parents=True,exist_ok=True)
    results=[]; failures=[]
    for iso,reporter,year,flow,product,partner_iso,partner in CASES:
        params={'reporterCode':reporter,'period':year,'flowCode':flow,'cmdCode':product,'partnerCode':partner,'partner2Code':0,'customsCode':'C00','motCode':0,'maxRecords':500}
        path=directory/f'{iso}-{year}-{flow}-{product}-{partner_iso}.json'
        if path.exists():
            raw=path.read_bytes(); payload=json.loads(raw)
            url=requests.Request('GET','https://comtradeapi.un.org/public/v1/preview/C/A/HS',params=params).prepare().url
        else:
            if '--cached-only' in sys.argv:
                failures.append({'case':path.stem,'status':'not_checked','note':'No retained response. Initial live run hit HTTP 429 at the third case; no further request in cached-only mode.'});continue
            response=requests.get('https://comtradeapi.un.org/public/v1/preview/C/A/HS',params=params,timeout=45)
            if response.status_code==429:
                failures.append({'case':path.stem,'status':429,'note':'Official rate limit reached; stopped without repeated requests.'});break
            response.raise_for_status(); raw=response.content; path.write_bytes(raw);payload=response.json();url=response.url
        data=payload['data']
        if len(data)!=1: raise ValueError(f'Expected one observation, got {len(data)}')
        official=Decimal(str(data[0]['primaryValue']))
        wits=Decimal(next(r['value_usd'] for r in rows if (r['reporter'],int(r['year']),r['flow'],r['product'],r['partner'])==(iso,year,flow,product,partner_iso)))
        difference=wits-official
        results.append({'case':path.stem,'url':url,'sha256':hashlib.sha256(raw).hexdigest(),'wits_usd':str(wits),'comtrade_usd':str(official),'difference_usd':str(difference),'within_wits_rounding_5_usd':abs(difference)<=Decimal('5.01'),
            'classification_wits':'H0','classification_comtrade':data[0]['classificationCode'],
            'note':'Comtrade original classification vs WITS H0; spot comparison only, not evidence of universal cross-classification equivalence.'})
        print(path.stem,results[-1]['within_wits_rounding_5_usd'],difference,flush=True);time.sleep(3)
    (directory/'report.json').write_text(json.dumps({'created_at':datetime.now(timezone.utc).isoformat(),'cases':results,'failures':failures,'limitation':f'计划六项，实际完成{len(results)}项抽样；仅检查金额与公开表舍入一致性，不代表全部记录认证。'},ensure_ascii=False,indent=2),encoding='utf-8')

if __name__=='__main__':main()

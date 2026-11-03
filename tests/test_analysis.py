import csv, io, json
from decimal import Decimal
from fractions import Fraction
import pytest
from backend.analysis import Spec, analyse
from backend.data import DataError, load_rows, get_dataset

HEADER='reporter,reporter_name,partner,partner_name,year,flow,product,product_name,classification,value_usd,status\n'

def fixture_rows():
    return load_rows((HEADER+'USA,美国,WLD,World,2019,M,0902,茶叶,H0,100,observed\nUSA,美国,WLD,World,2023,M,0902,茶叶,H0,150,observed\nUSA,美国,CHN,中国,2019,M,0902,茶叶,H0,20,observed\nUSA,美国,CHN,中国,2023,M,0902,茶叶,H0,45,observed\nUSA,美国,JPN,日本,2019,M,0902,茶叶,H0,80,observed\nUSA,美国,JPN,日本,2023,M,0902,茶叶,H0,105,observed\n').encode(),'fixture')

def calc(rows): return analyse(Spec(),(rows,{'name':'synthetic fixture','sources':[],'limitations':[]},'test-fixture'))

def test_decomposition_against_independent_fraction():
    r=calc(fixture_rows());p=next(p for p in r['partners'] if p['code']=='CHN')
    market=(Fraction(20,100)+Fraction(45,150))/2*(150-100)
    share=Fraction(100+150,2)*(Fraction(45,150)-Fraction(20,100))
    assert p['delta']==25
    assert p['market_component']==float(market)==12.5
    assert p['share_component']==float(share)==12.5
    assert p['share_change']==10
    assert r['structure']['change_residual']==0
    assert r['summary']['growth']==50

def test_missing_partner_not_zero_or_exit():
    rows=[x for x in fixture_rows() if not (x['partner']=='CHN' and x['year']==2023)]
    p=next(p for p in calc(rows)['partners'] if p['code']=='CHN')
    assert p['current'] is None and p['delta'] is None and p['status']=='unknown'

def test_explicit_zero_entry():
    rows=fixture_rows()
    for x in rows:
        if x['partner']=='CHN' and x['year']==2019:x['value']=Decimal(0)
    p=next(p for p in calc(rows)['partners'] if p['code']=='CHN')
    assert p['status']=='entry' and p['growth'] is None

def test_zero_denominator_no_fraction():
    rows=fixture_rows()
    for x in rows:
        if x['partner']=='WLD' and x['year']==2019:x['value']=Decimal(0)
    r=calc(rows);p=r['partners'][0]
    assert r['summary']['growth'] is None
    assert p['share0'] is None and p['market_component'] is None

def test_row_order_invariant():
    rows=fixture_rows(); a=calc(rows); b=calc(list(reversed(rows)))
    assert a['summary']==b['summary']
    assert [(p['code'],p['delta']) for p in a['partners']]==[(p['code'],p['delta']) for p in b['partners']]

def test_unit_scale_invariant():
    rows=fixture_rows();a=calc(rows)
    for x in rows:x['value']*=1000
    b=calc(rows)
    assert a['summary']['growth']==b['summary']['growth']
    assert [p['share_change'] for p in a['partners']]==[p['share_change'] for p in b['partners']]

def test_irrelevant_records_do_not_change_summary():
    rows=fixture_rows();a=calc(rows)
    rows.append(dict(rows[0],reporter='DEU',record_id='unrelated',value=Decimal('999999')))
    assert calc(rows)['summary']==a['summary']

def test_mixed_classification_rejected():
    rows=fixture_rows();rows[0]['classification']='H1'
    with pytest.raises(DataError,match='分类'):calc(rows)

def test_duplicate_rejected():
    rows=fixture_rows();rows.append(dict(rows[0],record_id='second-id'))
    with pytest.raises(DataError,match='重复'):calc(rows)

def test_region_aggregate_rejected():
    rows=fixture_rows();rows[2]['partner_type']='aggregate'
    with pytest.raises(DataError,match='区域'):calc(rows)

def test_unallocated_not_compared():
    rows=fixture_rows();rows[2]['partner_type']='unallocated';rows[3]['partner_type']='unallocated'
    r=calc(rows);assert all(p['code']!='CHN' for p in r['partners'])
    assert r['structure']['change_residual']==25

@pytest.mark.parametrize('patch',[{'products':['09','0902']},{'base_year':2023,'end_year':2019},{'products':[]},{'mode':'competition','flow':'X'},{'mode':'bilateral','partner':'USA'},{'reporters':['USA','USA']}])
def test_spec_rejects_invalid_scope(patch):
    with pytest.raises(ValueError):Spec(**patch)

@pytest.mark.parametrize('amount,status',[('NaN','observed'),('Infinity','observed'),('-1','observed'),('2','explicit_zero'),('1','missing'),('','observed')])
def test_nonfinite_negative_and_invalid_missing_rejected(amount,status):
    content=HEADER+f'USA,美国,WLD,World,2019,M,0902,茶叶,H0,{amount},{status}\n'
    with pytest.raises(DataError):load_rows(content.encode(),'fixture')

def test_hhi_not_faked_from_partial_table():
    assert calc(fixture_rows())['structure']['current']['hhi'] is None

def test_world_missing_preserves_local_computable_change():
    rows=[r for r in fixture_rows() if not (r['partner']=='WLD' and r['year']==2023)]
    r=calc(rows);p=next(p for p in r['partners'] if p['code']=='CHN')
    assert r['summary']['delta'] is None and p['delta']==25
    assert p['market_component'] is None

def test_real_sample_against_fraction():
    rows,manifest,sha=get_dataset('wits-core');r=analyse(Spec(),(rows,manifest,sha))
    def v(year,partner):return Fraction(next(x['value'] for x in rows if x['reporter']=='USA' and x['partner']==partner and x['year']==year and x['flow']=='M' and x['product']=='0902'))
    a,b,x,y=v(2019,'WLD'),v(2023,'WLD'),v(2019,'CHN'),v(2023,'CHN')
    p=next(p for p in r['partners'] if p['code']=='CHN')
    assert p['share_change']==float((y/b-x/a)*100)
    assert abs(p['market_component']+p['share_component']-p['delta'])<1e-7

def test_real_all_modes_and_product_basket():
    rows,manifest,sha=get_dataset('wits-core'); injected=(rows,manifest,sha)
    for mode in ['competition','bilateral','comparison']:
        r=analyse(Spec(mode=mode,products=['0901','0902','8703']),injected)
        assert r['evidence'] and r['series']
        if mode=='comparison':assert len(r['comparisons'])==3
        else:assert r['summary']['current'] is not None

"""Generate case-study drafts from actual deterministic results, not invented findings."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'.vendor'));sys.path.insert(0,str(ROOT))
from backend.analysis import Spec, analyse

cases=[('候选主案例：美国乘用车进口来源变化','wits-core','USA','8703'),
       ('对照案例：美国咖啡进口来源变化','wits-core','USA','0901'),
       ('迁移案例：加拿大含可可食品进口','wits-canada-cocoa','CAN','1806')]
text=['# 真实案例分析初稿\n','由当前程序实际计算生成，属于描述性分析开发材料，未经独立学术评审，不宣称AI效果或因果发现。\n']
for title,dataset,reporter,product in cases:
    r=analyse(Spec(dataset_id=dataset,reporter=reporter,products=[product]));s=r['summary']
    text.append(f'## {title}\n')
    text.append(f'范围：2019—2023，HS {product} / {r["classification"]}，报告国进口。\n')
    text.append(f'世界进口金额由{s["baseline"]:,.2f} USD变为{s["current"]:,.2f} USD，区间增长{s["growth"]:.2f}%。\n')
    text.append('|伙伴代码|金额变化/USD|份额变化/百分点|市场规模分量/USD|供应份额分量/USD|证据|\n|---|---:|---:|---:|---:|---|')
    ranking=sorted([p for p in r['partners'] if p['delta'] is not None],key=lambda p:abs(p['delta']),reverse=True)[:5]
    for p in ranking:
        text.append(f'|{p["code"]}|{p["delta"]:+,.2f}|{p["share_change"]:+.2f}|{p["market_component"]:+,.2f}|{p["share_component"]:+,.2f}|{p["evidence_id"]}|')
    text.append(f'\n总变化与全部两期可比伙伴变化合计的对账残差：{r["structure"]["change_residual"]:,.2f} USD。未把缺失伙伴按零处理。\n')
    text.append(f'数据SHA256：`{r["data_sha256"]}`。分析ID：`{r["analysis_id"]}`。\n')
    text.append('主要来源：\n')
    for source in r['sources']:
        if source['id'] in {f'{reporter}-2019-Imports-{product}',f'{reporter}-2023-Imports-{product}'}:
            text.append(f'- [{source["id"]}]({source["url"]})')
    text.append('\n可支持：比较金额、份额、分量方向及相对大小。不能直接支持：政策因果、产业竞争力、利润、实际需求量或质量提升。金额按名义美元和公开表精度理解。\n')
text.append('## 选题建议\n美国乘用车案例可用于展示不同供应国方向相反的份额变化与对称分解；咖啡和加拿大案例用于验证同一工具在其他商品及国家中的迁移。最终主案例仍需结合真实用户任务、商品边界和模型实际增益确定。\n')
(ROOT/'docs/案例分析初稿.md').write_text('\n'.join(text),encoding='utf-8')
print('Wrote 3 real case-study drafts')

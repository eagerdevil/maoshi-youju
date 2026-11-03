"""Curated research questions over retained data, not prewritten empirical findings."""
from .analysis import Spec

def cases():
    definitions=[
        ('us-cars','美国乘用车：市场扩大，供应格局怎样变？','比较供应国份额与金额变化，拆分市场规模和供应份额两个分量。',
         Spec(products=['8703']), 'KOR','markets','哪些供应国的金额变化与市场总体扩张方向不同？'),
        ('export-comparison','中德日乘用车出口：规模与增速分开看','使用各国报告的出口总额比较，不把所选国家合计视作全球市场。',
         Spec(mode='comparison',flow='X',products=['8703']),None,'overview','比较这些国家的出口变化，哪些结论需要谨慎解释？'),
        ('canada-cocoa','加拿大含可可食品：金额增长等于份额提高吗？','切换到不同国家与行业，观察供应金额和份额是否同向变化。',
         Spec(dataset_id='wits-canada-cocoa',reporter='CAN',reporters=['CAN'],partner='USA',products=['1806']),'USA','markets','美国供应金额与市场份额的变化是否一致？'),
    ]
    return [{'id':key,'title':title,'description':description,'spec':spec.model_dump(),'focus':focus,'tab':tab,'question':question} for key,title,description,spec,focus,tab,question in definitions]

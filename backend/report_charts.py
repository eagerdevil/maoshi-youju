"""Offline, deterministic SVG charts for exported HTML reports."""
from html import escape

COLORS=['#27796b','#c98258','#4e7396','#9a81a8','#b29d58','#718c7c']

def charts(result):
    years=result['series'];spec=result['spec']
    reporters=spec['reporters'] if spec['mode']=='comparison' else [spec['reporter']]
    values=[v for p in years for v in p['values'].values() if v is not None]
    maximum=max(values or [1]) or 1
    width,height,left,top,plotw,ploth=900,290,85,25,770,200
    svg=[f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="金额时间序列" style="width:100%;background:#f8faf5;border:1px solid #e2e9de;border-radius:8px">']
    for i in range(5):
        y=top+ploth-i/4*ploth;v=maximum*i/4
        svg.append(f'<line x1="{left}" x2="{left+plotw}" y1="{y}" y2="{y}" stroke="#e3e9df"/><text x="{left-10}" y="{y+4}" text-anchor="end" font-size="10" fill="#71866a">{v/1e6:,.1f}m</text>')
    for i,p in enumerate(years):
        x=left+i/max(1,len(years)-1)*plotw
        svg.append(f'<text x="{x}" y="{top+ploth+22}" text-anchor="middle" font-size="11" fill="#71866a">{p["year"]}</text>')
    for ri,reporter in enumerate(reporters):
        points=[]
        def flush():
            if points:svg.append(f'<polyline points="{" ".join(points)}" fill="none" stroke="{COLORS[ri%len(COLORS)]}" stroke-width="2.5"/>')
            points.clear()
        for i,p in enumerate(years):
            v=p['values'].get(reporter)
            if v is None:flush();continue
            x=left+i/max(1,len(years)-1)*plotw;y=top+ploth-v/maximum*ploth
            points.append(f'{x:.2f},{y:.2f}')
            svg.append(f'<circle cx="{x}" cy="{y}" r="3" fill="{COLORS[ri%len(COLORS)]}"><title>{escape(reporter)} {p["year"]}: {v:,.2f} USD</title></circle>')
        flush()
        name=escape(result['names'].get(reporter,reporter))
        svg.append(f'<text x="{left+ri*125}" y="{height-10}" font-size="11" fill="{COLORS[ri%len(COLORS)]}">{name}</text>')
    svg.append('</svg>')
    candidates=result['comparisons'] or result['partners']
    rows=sorted([p for p in candidates if p['delta'] is not None],key=lambda p:abs(p['delta']),reverse=True)[:8]
    maximum=max([abs(p['delta']) for p in rows] or [1]) or 1
    h=45+len(rows)*35
    bars=[f'<svg viewBox="0 0 900 {h}" role="img" aria-label="主要对象金额变化" style="width:100%;background:#f8faf5;border:1px solid #e2e9de;border-radius:8px">']
    center=450;scale=280/maximum
    bars.append(f'<line x1="{center}" x2="{center}" y1="10" y2="{h-20}" stroke="#b9c8b1"/>')
    for i,p in enumerate(rows):
        y=18+i*35;length=abs(p['delta'])*scale;x=center if p['delta']>=0 else center-length
        color='#428977' if p['delta']>=0 else '#cc9273'
        bars.append(f'<text x="15" y="{y+13}" font-size="10" fill="#5b7450">{escape(p["name"][:23])}</text><rect x="{x}" y="{y}" width="{length}" height="18" rx="2" fill="{color}"/><text x="745" y="{y+13}" font-size="10" fill="#5b7450">{p["delta"]:+,.0f}</text>')
    bars.append('</svg>')
    return '<h2>金额趋势 / USD，纵轴为百万美元</h2>'+''.join(svg)+'<h2>主要对象金额变化 / USD</h2>'+''.join(bars)

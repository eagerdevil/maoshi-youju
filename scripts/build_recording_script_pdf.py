"""Readable PDF editions of the approved recording script; no model calls."""
from pathlib import Path
import html
import re
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '.vendor'))
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle

SOURCE = ROOT / '参赛材料/0.5.4'
OUT = ROOT / 'output/pdf/recording-script'
pdfmetrics.registerFont(TTFont('CJKScript', 'C:/Windows/Fonts/msyh.ttc', subfontIndex=0))
pdfmetrics.registerFont(TTFont('CJKScriptBold', 'C:/Windows/Fonts/msyhbd.ttc', subfontIndex=0))
GREEN = colors.HexColor('#204c3d')
LIGHT = colors.HexColor('#eef4ee')
BODY = colors.HexColor('#273e36')
styles = {
    'title': ParagraphStyle('title', fontName='CJKScriptBold', fontSize=22, leading=32, textColor=GREEN, spaceAfter=14, wordWrap='CJK', keepWithNext=True),
    'h2': ParagraphStyle('h2', fontName='CJKScriptBold', fontSize=16, leading=25, textColor=GREEN, spaceBefore=12, spaceAfter=10, wordWrap='CJK', keepWithNext=True),
    'h3': ParagraphStyle('h3', fontName='CJKScriptBold', fontSize=14, leading=23, textColor=GREEN, spaceAfter=10, wordWrap='CJK', keepWithNext=True),
    'label': ParagraphStyle('label', fontName='CJKScriptBold', fontSize=11, leading=19, textColor=GREEN, spaceBefore=8, spaceAfter=6, wordWrap='CJK', keepWithNext=True),
    'body': ParagraphStyle('body', fontName='CJKScript', fontSize=10.5, leading=18, textColor=BODY, spaceAfter=7, wordWrap='CJK', splitLongWords=True),
    'speech': ParagraphStyle('speech', fontName='CJKScript', fontSize=12, leading=22, textColor=GREEN, backColor=LIGHT, borderPadding=8, leftIndent=9, rightIndent=9, spaceBefore=7, spaceAfter=12, wordWrap='CJK', splitLongWords=True),
    'table': ParagraphStyle('table', fontName='CJKScript', fontSize=9, leading=15, textColor=BODY, wordWrap='CJK', splitLongWords=True),
    'reading': ParagraphStyle('reading', fontName='CJKScript', fontSize=14, leading=26, textColor=BODY, spaceAfter=15, wordWrap='CJK', splitLongWords=True),
}


def clean(text):
    return text.replace('—', '-').replace('–', '-').replace('\u2011', '-').replace('**', '').replace('`', '')


def para(text, style='body'):
    return Paragraph(html.escape(clean(text)), styles[style])


def footer(canvas, doc):
    canvas.setStrokeColor(colors.HexColor('#dce5d5'))
    canvas.line(46, 39, A4[0]-46, 39)
    canvas.setFont('CJKScript', 8)
    canvas.setFillColor(colors.HexColor('#667e70'))
    canvas.drawString(46, 25, '贸势有据 / 小鸡快跑 / 0.5.4 / 2026-11-02 / 录屏辅助材料')
    canvas.drawRightString(A4[0]-46, 25, str(doc.page))


def write(name, elements):
    OUT.mkdir(parents=True, exist_ok=True)
    target = OUT / name
    SimpleDocTemplate(str(target), pagesize=A4, leftMargin=46, rightMargin=46,
        topMargin=43, bottomMargin=56, title=name.removesuffix('.pdf'), author='贸势有据项目').build(elements, onFirstPage=footer, onLaterPages=footer)
    shutil.copy2(target, SOURCE / name)
    return target


def detailed():
    lines = (SOURCE/'07-录屏逐字讲稿与点击动作.md').read_text(encoding='utf-8').splitlines()
    elements = []
    i = 0
    in_code = False
    scene_section = False
    while i < len(lines):
        line = lines[i].strip()
        i += 1
        if not line or line == '---':
            continue
        if line.startswith('```'):
            in_code = not in_code
            continue
        if in_code:
            elements.append(para(line, 'speech'))
        elif line.startswith('|'):
            rows = [[c.strip() for c in line.strip('|').split('|')]]
            while i < len(lines) and lines[i].strip().startswith('|'):
                cells = [c.strip() for c in lines[i].strip().strip('|').split('|')]
                if not all(re.fullmatch(r'[-: ]+', c) for c in cells):
                    rows.append(cells)
                i += 1
            width = A4[0]-92
            count = len(rows[0])
            widths = [width*.2, width*.25, width*.55] if count == 3 else [width/count]*count
            table = Table([[para(cell, 'table') for cell in row] for row in rows], colWidths=widths, repeatRows=1, hAlign='LEFT')
            table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),LIGHT), ('VALIGN',(0,0),(-1,-1),'TOP'),
                ('LINEBELOW',(0,0),(-1,-1),.4,colors.HexColor('#dce5d5')),
                ('LEFTPADDING',(0,0),(-1,-1),7), ('RIGHTPADDING',(0,0),(-1,-1),7),
                ('TOPPADDING',(0,0),(-1,-1),7), ('BOTTOMPADDING',(0,0),(-1,-1),7)]))
            elements += [table, Spacer(1, 9)]
        elif line.startswith('# '):
            elements.append(para(line[2:], 'title'))
        elif line.startswith('## '):
            if line.startswith('## 三、'):
                scene_section = True
                continue
            if re.match(r'## [二四五六]、', line):
                elements.append(PageBreak())
            elements.append(para(line[3:], 'h2'))
        elif line.startswith('### '):
            if line.startswith('### 第'):
                elements.append(PageBreak())
                if scene_section:
                    elements.append(para('三、分镜逐字讲稿', 'h2'))
                    scene_section = False
            elements.append(para(line[4:], 'h3'))
        elif line.startswith('**') and line.endswith('**'):
            elements.append(para(line, 'label'))
        elif line.startswith('>'):
            if line[1:].strip():
                elements.append(para(line[1:].strip(), 'speech'))
        else:
            elements.append(para(line))
    return write('07-录屏逐字讲稿与点击动作.pdf', elements)


def reading():
    parts = (SOURCE/'07-纯朗读稿.txt').read_text(encoding='utf-8').strip().split('\n\n')
    elements = [para('贸势有据｜纯朗读稿', 'title'), para('约7分钟演示 / 默认AI正常返回分支', 'h3'), para(parts[1], 'speech')]
    for text in parts[2:]:
        elements.append(para(text, 'reading'))
    return write('07-纯朗读稿.pdf', elements)


if __name__ == '__main__':
    for path in [detailed(), reading()]:
        print(path)

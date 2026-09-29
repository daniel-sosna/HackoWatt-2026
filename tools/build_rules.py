"""Build the English PDF from editable Markdown plus actual configuration/CSV."""
import csv
import json
from pathlib import Path
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,PageBreak,Table,TableStyle,Preformatted
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

ROOT=Path(__file__).resolve().parents[1]
font=Path('C:/Windows/Fonts/arial.ttf')
if font.exists():
    pdfmetrics.registerFont(TTFont('Body',str(font)))
    pdfmetrics.registerFont(TTFont('Bold','C:/Windows/Fonts/arialbd.ttf'))
else:
    pdfmetrics.registerFont(TTFont('Body',str(Path(__import__('reportlab').__file__).parent/'fonts/Vera.ttf')))
    pdfmetrics.registerFont(TTFont('Bold',str(Path(__import__('reportlab').__file__).parent/'fonts/VeraBd.ttf')))
styles={
 'body':ParagraphStyle('body',fontName='Body',fontSize=10,leading=13.4,spaceAfter=8),
 'title':ParagraphStyle('title',fontName='Bold',fontSize=21,leading=25,spaceAfter=15,keepWithNext=True),
 'h2':ParagraphStyle('h2',fontName='Bold',fontSize=12,leading=16,spaceBefore=7,spaceAfter=6,keepWithNext=True),
 'cell':ParagraphStyle('cell',fontName='Body',fontSize=8.3,leading=11),
 'header':ParagraphStyle('header',fontName='Bold',fontSize=8.3,leading=11),
 'math':ParagraphStyle('math',fontName='Body',fontSize=10,leading=14,spaceBefore=3,spaceAfter=9,leftIndent=12)}

def table(headers,rows,widths):
    cells=[[Paragraph(escape(str(v)),styles['header' if i==0 else 'cell']) for v in row] for i,row in enumerate([headers]+rows)]
    t=Table(cells,colWidths=[w*cm for w in widths],repeatRows=1,hAlign='LEFT')
    t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e7eef3')),('GRID',(0,0),(-1,-1),.35,colors.HexColor('#d9d9d9')),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('LEFTPADDING',(0,0),(-1,-1),5),('RIGHTPADDING',(0,0),(-1,-1),5),('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5)]))
    return t

story=[]
text=(ROOT/'docs/rules_v3.md').read_text(encoding='utf-8')
for paragraph in text.split('\n\n'):
    s=paragraph.strip()
    if not s:continue
    if s=='---':story.append(PageBreak());continue
    style='body'
    if s.startswith('# '):style='title';s=s[2:]
    elif s.startswith('## '):style='h2';s=s[3:]
    elif s.startswith('FORMULA: '):style='math';s=s[9:]
    story.append(Paragraph(escape(s).replace('\n',' '),styles[style]))

config=json.loads((ROOT/'config/default.json').read_text())
for section in ['house','behaviour','devices','thermal','weather','calendar']:
    if section not in ['weather','calendar']:
        story.append(PageBreak())
    else:
        story.append(Spacer(1,14))
    story.append(Paragraph('Parameter catalogue '+section,styles['title' if section not in ['weather','calendar'] else 'h2']))
    values=config[section]['parameters'] if section=='house' else config[section]
    rows=[]
    for k,v in values.items():
        rows.append([k,json.dumps(v,ensure_ascii=True)])
    story.append(table(['Parameter','Default value or sampling specification'],rows,[7.1,10.3]))
    if section=='house':
        story.append(Spacer(1,10));story.append(Paragraph('All house units are encoded in parameter names. Distribution bounds are assumed, not survey-derived. Overrides always win. The default mode is sample; manual_example.json is a complete fixed-house example.',styles['body']))
    if section=='weather':
        story.append(Paragraph('Observed timestamps with an explicit UTC offset are converted directly to UTC. Naive historical labels use the configured Europe/Warsaw policy. The supplied issued-weather forecast has naive Polish-local labels and is converted using Europe/Warsaw.',styles['body']))

with (ROOT/'data/raw/activity_time_use_full.csv').open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
for offset in range(0,len(rows),19):
    story.append(PageBreak());story.append(Paragraph(f'Eurostat source rows {offset+1} to {min(offset+19,len(rows))}',styles['title']))
    story.append(Paragraph('Exact source values. h:mm means hours and minutes. Rows overlap hierarchically; the appendix is not a set of independent daily events.',styles['body']))
    story.append(table(['Activity','Participation %','All persons h:mm','Participants h:mm'],[[r['Activity'],r['Participation_rate_pct'],r['Time_spent_all'],r['Participation_time_only_participants']] for r in rows[offset:offset+19]],[9,2.8,2.8,2.8]))

def footer(canvas,doc):
    canvas.saveState();canvas.setFont('Body',8);canvas.setFillColor(colors.HexColor('#617080'))
    canvas.drawString(1.8*cm,.8*cm,'HackoWatt Family | Implemented rules v3.2')
    canvas.drawRightString(A4[0]-1.8*cm,.8*cm,str(doc.page));canvas.restoreState()

target=ROOT/'docs/rules_v3.pdf'
SimpleDocTemplate(str(target),pagesize=A4,leftMargin=1.8*cm,rightMargin=1.8*cm,topMargin=1.7*cm,bottomMargin=1.7*cm,title='Family behaviour appliance and heating generation rules',author='HackoWatt team').build(story,onFirstPage=footer,onLaterPages=footer)
print(target)

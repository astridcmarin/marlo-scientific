"""Local PDF rendering of a saved payload; no queries or network access."""
import io
import json
from pathlib import Path
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from .workspaces import brief_tables, reference_urls, METRIC_LABELS

FONT_PATH=Path(__file__).parent/'fonts'


def render_brief_pdf(brief):
    for name,file in [('BriefSans','DejaVuSans.ttf'),('BriefSansBold','DejaVuSans-Bold.ttf')]:
        if name not in pdfmetrics.getRegisteredFontNames():pdfmetrics.registerFont(TTFont(name,str(FONT_PATH/file)))
    pdfmetrics.registerFontFamily('BriefSans',normal='BriefSans',bold='BriefSansBold')
    supported=pdfmetrics.getFont('BriefSans').face.charToGlyph
    unsupported=set()
    def text(value):
        value=str(value).translate({ord(c):'-' for c in '‐‑‒–—'})
        for c in value:
            if ord(c) not in supported and c not in '\n\r\t':unsupported.add(ord(c))
        return ''.join(c if ord(c) in supported or c in '\n\r\t' else f'[U+{ord(c):04X}]' for c in value)
    ink=colors.HexColor('#173b49');teal=colors.HexColor('#167989');muted=colors.HexColor('#586878')
    styles={
        'body':ParagraphStyle('body',fontName='BriefSans',fontSize=9,leading=13,textColor=ink,spaceAfter=7,splitLongWords=True),
        'small':ParagraphStyle('small',fontName='BriefSans',fontSize=7.7,leading=11,textColor=muted,spaceAfter=6,splitLongWords=True),
        'title':ParagraphStyle('title',fontName='BriefSansBold',fontSize=23,leading=29,textColor=ink,spaceAfter=14),
        'h1':ParagraphStyle('h1',fontName='BriefSansBold',fontSize=16,leading=21,textColor=ink,spaceAfter=10,keepWithNext=True),
        'h2':ParagraphStyle('h2',fontName='BriefSansBold',fontSize=11,leading=15,textColor=teal,spaceBefore=13,spaceAfter=7,keepWithNext=True),
        'cell':ParagraphStyle('cell',fontName='BriefSans',fontSize=8,leading=11,textColor=ink,splitLongWords=True),
        'head':ParagraphStyle('head',fontName='BriefSansBold',fontSize=8,leading=11,textColor=colors.white),
    }
    def p(value,style='body'):
        return Paragraph(escape(text(value)).replace('\n','<br/>'),styles[style])
    def table(headers,rows,widths=None):
        cols=len(headers)
        widths=widths or ([350,149] if cols==2 else [255]+[61]*(cols-1))
        def cell(value):
            shown=text(value)
            if len(shown)>800:shown=shown[:760]+'... [full text in evidence JSON]'
            return p(shown,'cell')
        data=[[p(v,'head') for v in headers]]+[[cell(v) for v in row] for row in rows]
        t=Table(data,colWidths=widths,repeatRows=1,hAlign='LEFT')
        t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),ink),('VALIGN',(0,0),(-1,-1),'TOP'),
            ('LEFTPADDING',(0,0),(-1,-1),9),('RIGHTPADDING',(0,0),(-1,-1),9),
            ('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7),
            ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.HexColor('#f0f5f7'),colors.white]),
            ('LINEBELOW',(0,0),(-1,0),.7,teal),('LINEBELOW',(0,1),(-1,-1),.3,colors.HexColor('#dbe4e8'))]))
        return t
    payload=brief.payload;story=[p('CLINICAL & REGULATORY INTELLIGENCE','small'),p(payload['title'],'title'),
        p(f"Saved brief #{brief.id} | {payload['saved_at_utc']} UTC",'small'),p(payload['limitation']),
        p('Analyst notes','h2')]
    for line in text(payload['notes'] or 'No analyst notes supplied.').splitlines():
        if not line:story.append(Spacer(1,5))
        for start in range(0,len(line),500):story.append(p(line[start:start+500]))
    story.append(p('Report contents','h2'))
    for i,c in enumerate(payload['cohorts'],1):
        s=c['summary'];story.append(p(f"[C{i}] Cohort #{s['cohort']['id']}: {s['cohort']['condition']} | {s['metrics']['total_trials']['value']:,} studies | {s['cohort']['scope']}"))
    story.append(p('Notes above are user-authored. Quantitative tables below use the saved source cohort. The JSON export preserves all group memberships, snapshot references, field/rule/catalog details, and pinned raw study objects.','small'))
    if len(payload['cohorts'])==2:
        a,b=payload['cohorts']
        overlap=len(set(a['summary']['evidence'])&set(b['summary']['evidence']))
        story.extend([p('Two-cohort descriptive comparison','h2'),table(['Measure','[C1]','[C2]'],
            [[label,a['summary']['metrics'][key]['value'],b['summary']['metrics'][key]['value']] for key,label in METRIC_LABELS.items()], [309,95,95]),
            p(f'Overlap: {overlap} NCT IDs occur in both cohorts. Query scopes and snapshots may differ. Counts are not a change over time, and name/country metrics are not trial counts.','small')])
    for i,c in enumerate(payload['cohorts'],1):
        s=c['summary'];meta=s['cohort'];story.extend([PageBreak(),p(f"[C{i}] {meta['condition']}",'h1'),
            p(f"Cohort #{meta['id']} | {meta['scope']} | Finished {meta['finished_at_utc']} UTC",'small'),
            p('Query parameters: '+json.dumps(meta['query_params'],ensure_ascii=False),'small'),
            p(f"Start-date bounds: {meta['start_year'] if meta['start_year'] is not None else 'All years'} to {meta['end_year'] if meta['end_year'] is not None else 'All years'}",'small')])
        for spec in brief_tables(c):
            story.extend([p(spec['title']+f' [C{i}]','h2'),table(spec['headers'],spec['rows'] or [['No reported categories',0]]),p(spec['note'],'small'),p('Method: '+spec['method'],'small')])
        if c['pinned_trials']:
            story.extend([p('Pinned study evidence','h2')])
            for j,row in enumerate(c['pinned_trials'],1):
                ref=row['evidence'];story.extend([p(f"[C{i}-T{j}] {row['nct_id']}: {row['title'] or 'Title not reported'}"),
                    p(f"Status: {row['status'] or 'Not reported'} | Lead sponsor: {row['sponsor'] or 'Not reported'}",'small'),
                    p(f"Snapshot #{ref['snapshot_id']} | Retrieved {ref['retrieved_at_utc']} UTC",'small'),
                    p('Raw source SHA256: '+ref['raw_study_sha256'],'small'),
                    p(f"Current record (may differ from retained evidence): https://clinicaltrials.gov/study/{row['nct_id']}",'small')])
        story.extend([p('Source and method references','h2'),p(f"[C{i}] ClinicalTrials.gov API v2, retained cohort #{meta['id']}. Query version: {meta['query_version']}. {len(s['evidence'])} snapshot references are preserved in the JSON export.",'small'),
            p('Source manifest SHA256: '+c['source_manifest_sha256'],'small')])
        times=[r['retrieved_at_utc'] for r in s['evidence'].values()]
        story.append(p('Snapshot retrieval range: '+(min(times)+' to '+max(times)+' UTC' if times else 'Empty cohort'),'small'))
        for key,report in c['reports'].items():
            identifiers={k:v for k,v in report.items() if ('version' in k or 'sha256' in k) and isinstance(v,str)}
            if 'reference' in report:identifiers.update({k:v for k,v in report['reference'].items() if ('version' in k or 'sha256' in k or k=='verified_on') and isinstance(v,str)})
            story.append(p(key.title()+': '+json.dumps(identifiers,ensure_ascii=False),'small'))
        story.append(p('Reference links identify the bundled sources; they can include products without name matches. Coverage tables define which references matched. Very long table labels are abbreviated; the evidence JSON retains their full text.','small'))
        for url in reference_urls(c['reports']):story.append(p(url,'small'))
    story.extend([p('Saved report provenance','h1'),p('Payload SHA256: '+brief.payload_sha256,'small'),
        p('Schema: '+payload['schema_version'],'small'),p('The saved payload supplies all values in this PDF. Reopening or downloading it does not rerun analyses, fetch registry updates or use newer catalogs. Save a new brief to capture another analysis.','body')])
    if unsupported:story.append(p('Font coverage: unsupported characters were shown as Unicode code points, such as [U+4E00]. Original text remains in the JSON export.','small'))
    stream=io.BytesIO()
    def footer(canvas,doc):
        canvas.saveState();canvas.setStrokeColor(teal);canvas.line(48,43,A4[0]-48,43)
        canvas.setFont('BriefSans',7);canvas.setFillColor(muted)
        canvas.drawString(48,30,f'Clinical Intelligence | Saved brief #{brief.id} | Frozen source evidence')
        canvas.drawRightString(A4[0]-48,30,str(doc.page));canvas.restoreState()
    doc=SimpleDocTemplate(stream,pagesize=A4,leftMargin=48,rightMargin=48,topMargin=48,bottomMargin=60,
        title=payload['title'],author='Clinical Intelligence',pageCompression=1,invariant=1)
    doc.build(story,onFirstPage=footer,onLaterPages=footer)
    return stream.getvalue()

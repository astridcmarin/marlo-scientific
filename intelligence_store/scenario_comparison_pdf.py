"""A summary PDF from a verified frozen comparison, with no source queries."""
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
from .regulatory import digest


def render_scenario_comparison_pdf(comparison):
    body = dict(comparison)
    expected = body.pop('comparison_sha256', None)
    if digest(body) != expected:
        raise ValueError('Comparison integrity check failed.')
    for side in comparison['scenarios']:
        if digest(side['payload']) != side['payload_sha256']:
            raise ValueError('Scenario integrity check failed.')
    fonts = Path(__file__).parent / 'fonts'
    for name, file in [('ScenarioSans', 'DejaVuSans.ttf'), ('ScenarioBold', 'DejaVuSans-Bold.ttf')]:
        if name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(name, str(fonts / file)))
    pdfmetrics.registerFontFamily('ScenarioSans', normal='ScenarioSans', bold='ScenarioBold')
    supported = pdfmetrics.getFont('ScenarioSans').face.charToGlyph
    unsupported = set()
    ink = colors.HexColor('#173b49')
    teal = colors.HexColor('#167989')
    styles = {key: ParagraphStyle(key, fontName=font, fontSize=size, leading=leading,
        textColor=color, spaceAfter=after, splitLongWords=True, keepWithNext=keep)
        for key, font, size, leading, color, after, keep in [
            ('body','ScenarioSans',9,13,ink,7,False),
            ('small','ScenarioSans',7.5,11,ink,6,False),
            ('title','ScenarioBold',23,28,ink,14,False),
            ('h1','ScenarioBold',16,21,ink,10,True),
            ('h2','ScenarioBold',11,15,teal,8,True),
            ('cell','ScenarioSans',8,11,ink,0,False),
            ('head','ScenarioBold',8,11,colors.white,0,False)]}

    def text(v):
        if v is None or v == '':
            v = 'Unknown / not supplied'
        elif isinstance(v, list):
            v = ', '.join(str(x) for x in v) or 'No names entered'
        value = str(v).translate({ord(c): '-' for c in '‐‑‒–—'})
        out = []
        for char in value:
            if ord(char) in supported or char in '\n\r\t':
                out.append(char)
            else:
                unsupported.add(ord(char)); out.append(f'[U+{ord(char):04X}]')
        return ''.join(out)

    def p(v, style='body'):
        return Paragraph(escape(text(v)).replace('\n', '<br/>'), styles[style])

    def table(headers, rows, widths):
        def cell(v):
            shown = text(v)
            if len(shown) > 600:
                shown = shown[:560] + '... [full value in comparison JSON]'
            return p(shown, 'cell')
        t = Table([[p(h, 'head') for h in headers]] + [[cell(v) for v in row] for row in rows],
                  colWidths=widths, repeatRows=1, hAlign='LEFT')
        t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),ink), ('VALIGN',(0,0),(-1,-1),'TOP'),
            ('LEFTPADDING',(0,0),(-1,-1),8), ('RIGHTPADDING',(0,0),(-1,-1),8),
            ('TOPPADDING',(0,0),(-1,-1),7), ('BOTTOMPADDING',(0,0),(-1,-1),7),
            ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.HexColor('#f0f5f7'),colors.white]),
            ('LINEBELOW',(0,1),(-1,-1),.3,colors.HexColor('#dbe4e8'))]))
        return t

    def paragraphs(v, style='body'):
        # Bounded paragraphs let long names/context flow across pages safely.
        shown = text(v)
        for i in range(0, len(shown), 500):
            story.append(p(shown[i:i+500], style))

    sides = comparison['scenarios']
    story = [p('CLINICAL & REGULATORY INTELLIGENCE', 'small'),
             p('Synthetic Scenario Comparison', 'title'),
             p(f"Frozen reports: left #{sides[0]['id']} | right #{sides[1]['id']}", 'small'),
             p('Synthetic Educational Patient Scenarios', 'h2'), p(comparison['limitation']),
             p('This PDF is a summary. Download the accompanying comparison JSON for all criteria records, source manifests and complete stored reports. Long table values may be abbreviated.', 'small'),
             p('Evidence and method context', 'h2')]
    context = comparison['context']
    story.append(p('Same source cohort, manifest and checked methods/catalogs.' if context['same_evidence_and_methods'] else
                   'Evidence or method context differs. Read each side independently; this is not a controlled comparison or a change over time.'))
    story.append(p(f"Same cohort ID: {context['same_cohort_id']} | Same source manifest: {context['same_source_manifest']}", 'small'))
    paragraphs('Differing method/catalog fields: ' + (', '.join(context['differing_provenance_fields']) or 'None among checked fields'), 'small')
    for label, side in zip(('Left', 'Right'), sides):
        r = side['payload']['analysis']['report']
        paragraphs(f"{label} #{side['id']}: {side['payload']['title']}")
        paragraphs(f"{r['selected_drug']['label']} | Cohort #{r['cohort']['id']}: {r['cohort']['condition']} | {r['cohort']['scope']} | Saved {side['payload']['saved_at_utc']} UTC", 'small')
    story.extend([PageBreak(), p('Synthetic inputs', 'h1'),
        table(['Input', 'Left', 'Right', 'Difference'],
              [[r['label'], *r['values'], 'Different' if r['different'] else 'Same'] for r in comparison['input_rows']], [125,142,142,90]),
        p('Read dose value and unit together; no unit conversion is applied. Medication order is preserved. Blank values remain unknown; missing medications are not evidence of no exposure.', 'small'),
        p('Descriptive reference counts', 'h2'),
        table(['Measure', 'Left', 'Right'], [[r['label'], *r['values']] for r in comparison['count_rows']], [309,95,95]),
        p('Age/sex groups partition each selected-name denominator. Within reported fields is not full eligibility. Medication reference coverage is not risk or compatibility.', 'small'),
        p(f"Shared selected-name NCT IDs: {comparison['selected_name_overlap']['count']}", 'small'),
        p(comparison['selected_name_overlap']['note'], 'small')])
    for label, side in zip(('Left', 'Right'), sides):
        r = side['payload']['analysis']['report']
        story.extend([PageBreak(), p(f"{label} frozen reference context", 'h1')])
        paragraphs(side['payload']['title'])
        paragraphs(r['limitation'], 'small')
        story.append(p('Medication references', 'h2'))
        if not r['medications']:
            story.append(p('No medication names entered. Concomitant exposure remains unassessed.'))
        for medication in r['medications']:
            paragraphs(medication['name'])
            story.append(p('Saved coverage: ' + medication['status'].replace('_', ' '), 'small'))
            rule = medication['reference']
            if rule:
                paragraphs(rule['finding_label']); paragraphs(rule['basis'])
                paragraphs(f"{rule['reference_product']} | Sections {', '.join(rule['sections'])} | SPL {rule['source']['label_version']}", 'small')
                paragraphs(rule['source']['url'], 'small')
            else:
                story.append(p('No selected separate-pair finding; this does not establish compatibility or absence of an interaction.', 'small'))
        safety = r['safety_reference']
        story.append(p('Selected label safety context', 'h2'))
        paragraphs(safety['reference_product'])
        boxed = safety['boxed_warning']['present']
        story.append(p('Boxed warning in selected reference: ' + ('Present' if boxed is True else 'Absent' if boxed is False else 'Not curated'), 'small'))
        paragraphs(safety['boxed_warning']['basis'], 'small')
        for warning in safety['selected_warnings']:
            paragraphs(warning['topic']); paragraphs(warning['basis'], 'small')
            paragraphs('Sections: ' + ', '.join(warning['sections']), 'small')
        paragraphs(f"SPL {safety['source']['label_version']} | Label date {safety['source']['label_effective_date']} | Checked {safety['source']['verified_on']}", 'small')
        paragraphs(safety['source']['url'], 'small')
        story.append(p('Selected topics only, not a complete label summary or profile-specific risk assessment. Product names do not establish formulation, route or regimen. Current links can show newer information.', 'small'))
        for rule in r['non_pair_references']:
            paragraphs(rule['title']); paragraphs(rule['basis'], 'small')
            paragraphs(f"{rule['kind_label']} | Sections {', '.join(rule['sections'])} | SPL {rule['source']['label_version']}", 'small')
            paragraphs(rule['source']['url'], 'small')
        story.append(p('Source query and provenance', 'h2'))
        paragraphs(json.dumps(r['cohort'], ensure_ascii=False, sort_keys=True), 'small')
        story.append(table(['Provenance field','Saved value'], sorted(r['provenance'].items()), [190,309]))
        paragraphs('Scenario report SHA256: ' + r['scenario_sha256'], 'small')
        paragraphs('Saved payload SHA256: ' + side['payload_sha256'], 'small')
        paragraphs('Source manifest SHA256: ' + side['payload']['analysis']['source_manifest_sha256'], 'small')
    story.extend([p('Comparison traceability', 'h2'), p(comparison['method_version'], 'small'),
                  p('Comparison SHA256: ' + expected, 'small'),
                  p('All values come from the two stored reports. No current registry fetch, catalog reload or clinical analysis is performed. Raw source objects are not duplicated here; retain the original snapshot database. Digests detect accidental changes, not authenticity.', 'small')])
    if unsupported:
        story.append(p('Font coverage: unsupported characters appear as Unicode code points such as [U+4E00]. The comparison JSON retains original text.', 'small'))
    stream = io.BytesIO()
    def footer(canvas, doc):
        canvas.saveState(); canvas.setStrokeColor(teal); canvas.line(48,43,A4[0]-48,43)
        canvas.setFont('ScenarioSans',7); canvas.setFillColor(ink)
        canvas.drawString(48,30,f"Synthetic scenarios #{sides[0]['id']} / #{sides[1]['id']} | Frozen reference summary")
        canvas.drawRightString(A4[0]-48,30,str(doc.page)); canvas.restoreState()
    doc = SimpleDocTemplate(stream, pagesize=A4, leftMargin=48, rightMargin=48,
        topMargin=48, bottomMargin=60, title='Synthetic Scenario Comparison',
        author='Clinical Intelligence', pageCompression=1, invariant=1)
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return stream.getvalue()

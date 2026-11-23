"""Write the owner's review page for the label ingestion pilot: one self-contained HTML file, no network.

    python3 scripts/label_pilot_review_page.py intelligence_store/data/label_pilot_review_sheet_v1.json OUTPUT.html

The page shows each drawn section as the platform extracted it, with a link to the same label version on
DailyMed. For each, the owner records match, error (with its kind) or not reviewable, and downloads the
completed sheet as JSON. Answers are kept in the browser between visits. The rule is applied afterwards by
label_pilot.evaluate, never by the page.
"""
import html
import json
import sys
from pathlib import Path

ERROR_KINDS = ('text_missing', 'text_added', 'text_changed', 'order_wrong', 'heading_wrong', 'code_wrong',
               'table_unreadable', 'other')

PAGE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>Label pilot review</title>
<style>
body{font:15px/1.5 -apple-system,Segoe UI,sans-serif;max-width:900px;margin:2rem auto;padding:0 1rem;color:#222}
.item{border:1px solid #ccc;border-radius:6px;padding:1rem;margin:1.2rem 0}
.item.done{border-color:#2a7}
.meta{color:#555;font-size:13px}
pre{white-space:pre-wrap;background:#f6f6f6;padding:.8rem;border-radius:4px;font:14px/1.45 Menlo,monospace}
.bar{position:sticky;top:0;background:#fff;padding:.6rem 0;border-bottom:1px solid #ddd;z-index:1}
label{margin-right:1rem}
.rules{background:#fffbe6;border:1px solid #e6d57a;padding:.6rem 1rem;border-radius:4px}
</style></head><body>
<h1>Label ingestion pilot: section review</h1>
<div class="rules"><p><b>For each section</b>, open the label on DailyMed (same set ID and version) and find the section by its heading.
Mark <b>match</b> if the text is complete, in order, with nothing added, the heading is the printed heading, and the section code fits the section.
Otherwise mark <b>error</b> and choose its kind. Mark <b>not reviewable</b> only if DailyMed cannot show that version. A section shown as "(no heading)" is an unheaded part of a larger section: find it with your browser's search (Cmd-F) on its first words.</p>
<p><b>Not errors</b> (the plan's conventions): spaces and line breaks; tables written between [Table] and [End table], one row per line, cells joined by " | ";
superscript written ^(text), subscript _(text); images written [Image]; a footnote's text written where it is anchored as [Footnote: text], a reference to an earlier footnote as [See footnote];
subsections appearing in their own rows rather than in their parent's; Highlights not extracted.</p>
<p>The first 80 reviewable sections count; the last 20 are spares, needed only if some are not reviewable. Answers are saved in this browser; press <b>Download</b> when done and send the file.</p></div>
<div class="bar"><span id="progress"></span> <button onclick="download()">Download completed sheet</button></div>
__ITEMS__
<script>
const KEY='label-pilot-review-v1';
const items=__DATA__;
let state={};try{state=JSON.parse(localStorage.getItem(KEY)||'{}')}catch(e){}
function save(){try{localStorage.setItem(KEY,JSON.stringify(state))}catch(e){};render()}
function set(d,f,v){state[d]=state[d]||{};state[d][f]=v;save()}
function render(){let done=0;for(const it of items){const s=state[it.draw]||{};const el=document.getElementById('i'+it.draw);
 const ok=s.verdict&&(s.verdict!=='error'||s.error_kind);el.classList.toggle('done',!!ok);if(ok&&it.draw<=80)done++;
 for(const r of el.querySelectorAll('input[type=radio]'))r.checked=(s.verdict===r.value);
 const k=el.querySelector('select');k.value=s.error_kind||'';k.disabled=(s.verdict!=='error');
 el.querySelector('textarea').value=s.note||''}
 document.getElementById('progress').textContent=done+' of the first 80 answered'}
function download(){const out=items.map(it=>{const s=state[it.draw]||{};return Object.assign({},it.record,{verdict:s.verdict||null,
 error_kind:s.verdict==='error'?(s.error_kind||null):null,note:s.note||null})});
 const blob=new Blob([JSON.stringify({schema_version:'label-pilot-review-record-v1',reviewed_by:'owner',items:out},null,1)],{type:'application/json'});
 const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='label_pilot_review_record_v1.json';a.click()}
render();
</script></body></html>"""


def item_html(it):
    d = it['draw']
    kinds = ''.join(f'<option value="{k}">{k.replace("_", " ")}</option>' for k in ERROR_KINDS)
    lookup = f'https://dailymed.nlm.nih.gov/dailymed/lookup.cfm?setid={it["set_id"]}&version={it["version"]}'
    spare = ' (spare)' if d > 80 else ''
    return (f'<div class="item" id="i{d}"><h3>Section {d}{spare}: {html.escape(it["heading"] or "(no heading)")}</h3>'
            f'<div class="meta">{html.escape(it["label_title"][:200])}<br>Set ID {it["set_id"]}, version {it["version"]}; '
            f'section code {html.escape(str(it["code"]))} {html.escape(it["code_name"] or "")} · '
            f'<a href="{lookup}" target="_blank" rel="noopener">open this version on DailyMed</a></div>'
            f'<pre>{html.escape(it["text"])}</pre>'
            + ''.join(f'<label><input type="radio" name="v{d}" value="{v}" onchange="set({d},\'verdict\',this.value)"> {v.replace("_", " ")}</label>'
                      for v in ('match', 'error', 'not_reviewable'))
            + f' <select onchange="set({d},\'error_kind\',this.value)"><option value="">error kind…</option>{kinds}</select>'
            f'<br><textarea rows="2" cols="80" placeholder="note (optional)" onchange="set({d},\'note\',this.value)"></textarea></div>')


def main(sheet_path, out_path):
    sheet = json.loads(Path(sheet_path).read_text(encoding='utf-8'))
    data = [{'draw': it['draw'], 'record': {k: it[k] for k in ('draw', 'set_id', 'version', 'method_version', 'ord')}} for it in sheet]
    page = PAGE.replace('__ITEMS__', '\n'.join(item_html(it) for it in sheet)).replace(
        '__DATA__', json.dumps(data).replace('</', '<\\/'))
    Path(out_path).write_text(page, encoding='utf-8')
    print(f'wrote {out_path} ({len(sheet)} sections)')


if __name__ == '__main__':
    main(*sys.argv[1:3])

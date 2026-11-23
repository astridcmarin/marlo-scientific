"""Read a DailyMed structured product label (SPL) into verbatim sections, ingredients and marketing data.

Decision 0007 (every US prescription label, verbatim, review state shown) and decision 0009 (label content in
insert-only tables, rebuilt from DailyMed files listed in a pinned manifest). This module only reads; it never
summarises, translates or corrects label text.

Text rules (method spl-text-v1), fixed in the pilot plan so a reviewer knows what is not an addition:
- Inline text is kept in document order; runs of whitespace become one space, and lines are trimmed.
- A paragraph, list item, caption or table row ends a line.
- A table is written between the lines "[Table]" and "[End table]", one row per line, cells joined by " | ".
- Superscript text is written as ^(text) and subscript as _(text), so "m^(2)" is "m2" with a superscript 2.
- An image is written as [Image]. A footnote's text is written where it is anchored, as [Footnote: text]; a
  reference to an earlier footnote is written as [See footnote].
- A subsection's text belongs to the subsection's own row, not to its parent's.
- Highlights (<excerpt>) are not extracted in v1; the section row records how many it skipped.
"""
import hashlib
import io
import re
import zipfile
import xml.etree.ElementTree as ET

NS = {'v3': 'urn:hl7-org:v3'}
V3 = '{urn:hl7-org:v3}'
METHOD_VERSION = 'spl-text-v1'
LOINC = '2.16.840.1.113883.6.1'
UNII = '2.16.840.1.113883.4.9'
RX_DOCUMENT_CODE = '34391-3'  # HUMAN PRESCRIPTION DRUG LABEL
ACTIVE_CLASS_CODES = ('ACTIB', 'ACTIM', 'ACTIR')
BRAND_CATEGORIES = ('NDA', 'BLA')
GENERIC_CATEGORIES = ('ANDA', 'NDA AUTHORIZED GENERIC')
BLOCK = {'paragraph', 'item', 'caption', 'tr', 'br'}
_WS = re.compile(r'\s+')


class SplError(ValueError):
    pass


def parse_xml(raw):
    """Parse SPL bytes; a document declaring a DTD or entities is refused rather than expanded."""
    head = raw[:4096].upper()
    if b'<!DOCTYPE' in head or b'<!ENTITY' in raw.upper():
        raise SplError('SPL declares a DTD or entities; refused.')
    try:
        return ET.fromstring(raw)
    except ET.ParseError as exc:
        raise SplError(f'SPL is not well-formed XML: {exc}') from exc


def xml_from_zip(raw_zip):
    """The single XML member of a DailyMed per-label zip, as bytes, with its member name."""
    try:
        with zipfile.ZipFile(io.BytesIO(raw_zip)) as z:
            xml = [n for n in z.namelist() if n.lower().endswith('.xml') and '/' not in n.strip('/')]
            if len(xml) != 1:
                raise SplError(f'Expected one XML file in the zip, found {len(xml)}.')
            return xml[0], z.read(xml[0])
    except zipfile.BadZipFile as exc:
        raise SplError(f'Not a readable zip file: {exc}') from exc


def _local(tag):
    return tag.rsplit('}', 1)[-1] if isinstance(tag, str) else ''


def _attr(el, path, name):
    found = el.find(path, NS) if el is not None else None
    return found.get(name) if found is not None else None


def _inline(el):
    """Inline text of an element and its inline children, with sup/sub/image markers; tail handled by caller."""
    parts = [el.text or '']
    for child in el:
        tag = _local(child.tag)
        if tag in ('sup',):
            parts.append('^(' + _inline(child).strip() + ')')
        elif tag in ('sub',):
            parts.append('_(' + _inline(child).strip() + ')')
        elif tag == 'renderMultiMedia':
            parts.append(' [Image] ')
        elif tag in BLOCK or tag in ('list', 'table', 'paragraph'):
            parts.append('\n' + _render(child) + '\n')
        elif tag == 'footnote':
            parts.append(' [Footnote: ' + _clean(_inline(child)).replace('\n', ' ') + '] ')
        elif tag == 'footnoteRef':
            parts.append(' [See footnote] ')
        else:
            parts.append(_inline(child))
        parts.append(child.tail or '')
    return ''.join(parts)


def _render(el):
    tag = _local(el.tag)
    if tag == 'table':
        rows = []
        for tr in el.iter(V3 + 'tr'):
            cells = [_clean(_inline(td)) for td in tr if _local(td.tag) in ('td', 'th')]
            rows.append(' | '.join(cells))
        caption = el.find('v3:caption', NS)
        head = [_clean(_inline(caption))] if caption is not None else []
        return '\n'.join(['[Table]'] + head + rows + ['[End table]'])
    if tag == 'list':
        return '\n'.join(_clean(_inline(item)) for item in el.findall('v3:item', NS))
    if tag == 'br':
        return ''
    if tag == 'renderMultiMedia':
        return '[Image]'
    return _inline(el)


def _clean(text):
    lines = [_WS.sub(' ', line).strip() for line in text.split('\n')]
    return '\n'.join(line for line in lines if line)


def section_text(text_el):
    """Verbatim text of one <text> element under the spl-text-v1 rules."""
    if text_el is None:
        return ''
    out = [text_el.text or '']
    for child in text_el:
        out.append('\n' + _render(child) + '\n')
        out.append(child.tail or '')
    return _clean(''.join(out))


def _sections(parent, parent_ord, rows, counter):
    for comp in parent.findall('v3:component', NS):
        sec = comp.find('v3:section', NS)
        if sec is None:
            continue
        ord_ = counter[0]
        counter[0] += 1
        code = sec.find('v3:code', NS)
        title = sec.find('v3:title', NS)
        text = section_text(sec.find('v3:text', NS))
        rows.append({'ord': ord_, 'parent_ord': parent_ord,
                     'code': code.get('code') if code is not None else None,
                     'code_system': code.get('codeSystem') if code is not None else None,
                     'code_name': code.get('displayName') if code is not None else None,
                     'heading': _clean(_inline(title)) if title is not None else '',
                     'text': text, 'text_sha256': hashlib.sha256(text.encode('utf-8')).hexdigest(),
                     'excerpts_skipped': len(sec.findall('v3:excerpt', NS))})
        _sections(sec, ord_, rows, counter)


def _products(root):
    categories, applications, ingredients = set(), set(), {}
    for prod in root.iter(V3 + 'manufacturedProduct'):
        for approval in prod.findall('v3:subjectOf/v3:approval', NS):
            name = _attr(approval, 'v3:code', 'displayName')
            if name:
                categories.add(name.strip().upper())
            ext = _attr(approval, 'v3:id', 'extension')
            if ext:
                applications.add(ext.strip())
        for ing in prod.findall('v3:ingredient', NS):
            if ing.get('classCode') not in ACTIVE_CLASS_CODES:
                continue
            sub = ing.find('v3:ingredientSubstance', NS)
            code = sub.find('v3:code', NS) if sub is not None else None
            if code is None or code.get('codeSystem') != UNII:
                continue
            nm = sub.find('v3:name', NS)
            ingredients[code.get('code')] = _clean(nm.text or '') if nm is not None else ''
    return sorted(categories), sorted(applications), [{'unii': k, 'name': v} for k, v in sorted(ingredients.items())]


def category_class(categories):
    """brand if any marketing category is NDA or BLA; generic if all are ANDA or NDA authorized generic."""
    if any(c in BRAND_CATEGORIES for c in categories):
        return 'brand'
    if categories and all(c in GENERIC_CATEGORIES for c in categories):
        return 'generic'
    return 'other'


def read_label(raw_xml):
    """Everything the tables hold for one label version. Raises SplError for anything it cannot read."""
    root = parse_xml(raw_xml)
    if _local(root.tag) != 'document' or not root.tag.startswith(V3):
        raise SplError('Not an HL7 v3 SPL document.')
    set_id = _attr(root, 'v3:setId', 'root')
    version = _attr(root, 'v3:versionNumber', 'value')
    if not set_id or not version:
        raise SplError('SPL lacks a set ID or version number.')
    body = root.find('v3:component/v3:structuredBody', NS)
    if body is None:
        raise SplError('SPL has no structured body.')
    rows = []
    _sections(body, None, rows, [0])
    categories, applications, ingredients = _products(root)
    title = root.find('v3:title', NS)
    return {'set_id': set_id.lower(), 'version': int(version),
            'document_id': (_attr(root, 'v3:id', 'root') or '').lower(),
            'document_type_code': _attr(root, 'v3:code', 'code'),
            'effective_time': _attr(root, 'v3:effectiveTime', 'value'),
            'title': _clean(_inline(title)) if title is not None else '',
            'marketing_categories': categories, 'category_class': category_class(categories),
            'application_numbers': applications, 'ingredients': ingredients,
            'sections': rows, 'xml_sha256': hashlib.sha256(raw_xml).hexdigest(),
            'method_version': METHOD_VERSION}

"""Phase 4.1c: self-review of the reference annotation before export.

Shows the annotator her own work only: the criteria text with every recorded sentence highlighted, what was recorded
for each criterion type, and simple consistency prompts computed from the annotation and the text. Nothing here
reads or runs the extractor; the prompts are questions to look at, not corrections. A trial marked as reviewed keeps
the time of the mark; a correction after that is logged as usual by eligibility_annotations.save_annotation.
"""
import re
import unicodedata

from . import eligibility_annotations as ea

# Measure names only (no numbers), to point at criteria that may have been missed when a type is marked not stated.
MEASURE_WORDS = {
    'kidney_function_min': r'creatinine\s+clearance|\bcrcl\b|\begfr\b|\bgfr\b|glomerular',
    'creatinine_max': r'creatinine(?!\s+clearance)',
    'anc_min': r'neutrophil|\banc\b|granulocyte',
    'platelets_min': r'platelet|\bplt\b',
    'hemoglobin_min': r'ha?emoglobin|\bhgb\b|\bhb\b',
    'bilirubin_max': r'bilirubin',
    'ast_alt_max': r'\bast\b|\balt\b|sgot|sgpt|transaminase|aminotransferase',
    'ecog_max': r'\becog\b|performance\s+status|zubrod',
}
_EXCLUSION_HEADER = re.compile(r'^\s*[*#\-\s]*(?:key\s+)?exclusion\s+criteria', re.I | re.M)
_LOWER_BOUND = ('>=', '>')
_SYMBOL = {'>=': '≥', '<=': '≤', '>': '>', '<': '<'}


def _normal_map(text):
    """The annotation page's normalisation (NFKC, casefold, '*' as space, whitespace collapsed), with each
    normalised character mapped back to its position in the original text."""
    out, where, last_space = [], [], True
    for i, ch in enumerate(text or ''):
        for c in unicodedata.normalize('NFKC', ch).casefold():
            c = ' ' if c == '*' or c.isspace() else c
            if c == ' ':
                if last_space:
                    continue
                last_space = True
            else:
                last_space = False
            out.append(c)
            where.append(i)
    return ''.join(out), where


def locate(text, sentence):
    """(start, end) of the recorded sentence in the original text, or None."""
    norm, where = _normal_map(text)
    needle = ' '.join(unicodedata.normalize('NFKC', sentence or '').casefold().replace('*', ' ').split())
    if not needle:
        return None
    at = norm.find(needle)
    if at < 0:
        return None
    return where[at], where[at + len(needle) - 1] + 1


def section_at(text, position):
    """Which section a position in the text falls in, by the first 'Exclusion Criteria' heading."""
    m = _EXCLUSION_HEADER.search(text or '')
    return 'exclusion' if m and position >= m.start() else 'inclusion'


def highlighted(text, annotation):
    """The criteria text as pieces [(text, [type labels])], each recorded sentence marked with its types."""
    marks = [set() for _ in (text or '')]
    for key, entry in annotation.items():
        for value in entry.get('values', []):
            span = locate(text, value.get('sentence'))
            if span:
                for i in range(*span):
                    marks[i].add(key)
    pieces, start = [], 0
    for i in range(1, len(marks) + 1):
        if i == len(marks) or marks[i] != marks[start]:
            pieces.append((text[start:i], sorted(marks[start])))
            start = i
    return pieces


def _written_as_in_sentence(value):
    """True when the recorded comparator appears as a symbol in the sentence (registry escapes and ≥/≤ undone)."""
    sentence = (value.get('sentence') or '').replace('\\', '').replace('≥', '>=').replace('≤', '<=')
    token = {'>=': r'>=', '<=': r'<=', '>': r'>(?!=)', '<': r'<(?!=)'}[value['comparator']]
    return re.search(token, sentence) is not None


_FLIP = {'>=': '<', '>': '<=', '<=': '>', '<': '>='}
_TOKEN = {'>=': r'>=|=>|≥|=\s*>', '<=': r'<=|=<|≤|=\s*<', '>': r'>(?!\s*=)', '<': r'<(?!\s*=)'}


def _symbols_in(sentence):
    s = (sentence or '').replace('\\', '')
    s = re.sub(r'(?<![<>=])=(?!\s*[<>])', ' ', s)          # a lone '=' is not a comparator
    found = set()
    for comp in ('>=', '<=', '>', '<'):
        if re.search(_TOKEN[comp], s):
            found.add(comp)
    if '>=' in found:
        found.discard('>') if not re.search(r'>(?!\s*=)', s.replace('=>', '')) else None
    if '<=' in found:
        found.discard('<') if not re.search(r'<(?!\s*=)', s.replace('=<', '')) else None
    return found


def _strictness_mismatch(value):
    """Recorded ≥ where the sentence (after turning exclusion into the eligible side) says >, or ≤ vs <."""
    symbols = _symbols_in(value.get('sentence'))
    if not symbols:
        return None            # written in words ("at least"); nothing to compare
    recorded = value['comparator']
    expected = _FLIP[recorded] if value['section'] == 'exclusion' else recorded
    if expected in symbols:
        return None
    same_direction = {'>=': '>', '>': '>=', '<=': '<', '<': '<='}[expected]
    if same_direction in symbols:
        shown = _SYMBOL[recorded]
        should = _SYMBOL[_FLIP[same_direction]] if value['section'] == 'exclusion' else _SYMBOL[same_direction]
        return (f"recorded {shown}, but the sentence uses {_SYMBOL[same_direction]}"
                + (" (in exclusion, the eligible side of that is " + should + ")" if value['section'] == 'exclusion' else '')
                + f". Should it be {should}?")
    return None


def prompts(text, annotation):
    """Questions worth a second look, per criterion type; drawn only from the annotation and the text."""
    found = {}
    for key, entry in annotation.items():
        notes = []
        spec = ea.TYPES[key]
        lower_type = key.endswith('_min')
        for n, value in enumerate(entry.get('values', []), start=1):
            label = f'Value {n}' if len(entry['values']) > 1 else 'The value'
            if (value['comparator'] in _LOWER_BOUND) != lower_type:
                notes.append(f"{label} is {'an upper' if lower_type else 'a lower'} bound ({_SYMBOL[value['comparator']]} {value['value']}) "
                             f"for a {'minimum' if lower_type else 'maximum'}. Is that the eligible side?")
            span = locate(text, value.get('sentence'))
            if span and section_at(text, span[0]) != value['section']:
                notes.append(f"{label} is recorded as {value['section']}, but its sentence is under the "
                             f"{section_at(text, span[0])} heading.")
            strictness = _strictness_mismatch(value)
            if strictness:
                notes.append(f"{label}: {strictness}")
            if value['section'] == 'exclusion' and _written_as_in_sentence(value):
                notes.append(f"{label} is from the exclusion section and uses the same comparator as the sentence "
                             f"({_SYMBOL[value['comparator']]}). The guide records the eligible side, which is usually the opposite.")
            if value['unit'] == 'other' and not entry.get('note'):
                notes.append(f"{label} has unit 'other' and no note saying what the unit is.")
            number = value['value'].rstrip('0').rstrip('.') if '.' in value['value'] else value['value']
            if not (value['unit'] == 'x ULN' and float(value['value']) == 1.0) and not re.search(r'(?<![\d.])' + re.escape(number) + r'(?:\.0+)?(?![\d])', value.get('sentence', '').replace(',', '')):
                notes.append(f"{label} ({value['value']}) does not appear in its sentence as written.")
        if entry['status'] == 'not_stated':
            mentions = len(re.findall(MEASURE_WORDS[key], text or '', re.I))
            if mentions:
                notes.append(f"Marked not stated, but the text names this measure {mentions} time{'s' if mentions != 1 else ''} "
                             f"(highlighted in grey). Is there a number?")
        if entry['status'] == 'multiple' and len({(v['comparator'], v['value'], v['unit']) for v in entry['values']}) < 2:
            notes.append("Marked multiple, but the values recorded are the same.")
        if 'equations' in spec and entry.get('values') and entry.get('equation') == 'not_stated':
            sentence_text = ' '.join(v.get('sentence', '') for v in entry['values'])
            if re.search(r'cockcroft|cockroft|gault|mdrd|ckd[\s-]*epi|24[\s-]*h', sentence_text, re.I):
                notes.append('Estimating method is "not stated", but the sentence names one.')
        if notes:
            found[key] = notes
    return found


def mention_spans(text, annotation):
    """Character positions of measure names for types marked not stated (shown in grey)."""
    spans = []
    for key, entry in annotation.items():
        if entry['status'] == 'not_stated':
            spans += [(m.start(), m.end()) for m in re.finditer(MEASURE_WORDS[key], text or '', re.I)]
    return spans


def pieces_with_mentions(text, annotation):
    """highlighted() pieces, further split so that measure names of not-stated types are marked 'mention'."""
    flags = [False] * len(text or '')
    for a, b in mention_spans(text, annotation):
        for i in range(a, b):
            flags[i] = True
    out, pos = [], 0
    for piece, keys in highlighted(text, annotation):
        start = pos
        for i in range(len(piece) + 1):
            j = pos + i
            if i == len(piece) or (i and flags[j] != flags[j - 1]):
                if j > start:
                    out.append({'text': text[start:j], 'types': keys, 'mention': flags[start]})
                start = j
        pos += len(piece)
    return out


def describe(entry):
    """One line for the overview: '≤ 2 score' or 'not stated'."""
    if not entry['values']:
        return entry['status'].replace('_', ' ')
    parts = [f"{_SYMBOL[v['comparator']]} {v['value']} {v['unit']}" for v in entry['values']]
    text = '; '.join(parts)
    return text if entry['status'] == 'stated' else f"{entry['status']}: {text}"

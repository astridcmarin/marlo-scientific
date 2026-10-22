"""Phase 4.1d: rule-based extraction of eligibility thresholds from registered criteria text.

Written and tuned only on the 200-trial development set listed in eligibility_validation_sample_v1.json; the
validation sample's criteria text was not read. Output follows the annotation guide: for each of eight criterion types a status and values, each
value written as the condition a patient must meet to be *eligible* (comparators of exclusion criteria are flipped),
with the unit as written (mapped to the guide's list), the section and the source segment.

How it works, in order:
1. Clean the text: undo the registry's markdown escaping, normalise Unicode and spelled-out comparators.
2. Split it into segments (bullets, lines, ';' clauses), tracking the inclusion/exclusion section.
3. In each segment, find a keyword for a criterion type and the first comparator-number-unit after it, before the next
   keyword of another type ("bilirubin or AST > 3 x ULN" gives both the value). Values inside a conditional
   parenthesis or after 'if'/'unless'/'except'/'in whom' are qualifiers and are skipped, as is a second value for a
   measure in the same clause (usually the same value in another unit, or an exception).
4. Exclusion criteria, and inclusion criteria starting with 'No ...', are turned into the eligible side. A minimum type
   keeps only lower bounds and a maximum type only upper bounds: "Renal insufficiency: CrCl < 40" in a disease
   definition, or "ECOG >= 2" in an inclusion list, is not read as a threshold.
5. Combine: one distinct value -> stated; several -> multiple; none -> not_stated. The extractor never says 'unclear'.

Known limits seen in the development set: thresholds written before the measure ("> 1.5 x ULN total bilirubin"),
thresholds given only for a subgroup or cohort beyond the first, registry entries that list adequate values under
the exclusion heading, and trials whose population is defined by impaired function (an eligible upper bound on
CrCl) are missed or dropped.
"""
import re
import unicodedata

VERSION = 'eligibility-extractor-v1.0'

# ---------------------------------------------------------------- cleaning
_ESCAPES = [(r'\>', '>'), (r'\<', '<'), (r'\^', '^'), (r'\[', '['), (r'\]', ']'), (r'\*', '*'), (r'\_', '_'), (r'\=', '=')]
_WORD_COMPARATORS = [
    (r'greater\s+or\s+equal\s+to|higher\s+or\s+equal\s+to|greater than or equal to|more than or equal to|equal to or greater than|equal or greater than|equal to or more than|not less than|no less than|at least|minimum of|≧|=>|>=|=\s*>', ' >= '),
    (r'less\s+or\s+equal\s+to|lower\s+or\s+equal\s+to|equal\s+or\s+lower\s+than|less than or equal to|equal to or less than|equal or less than|not more than|no more than|not greater than|no greater than|not exceeding|not to exceed|up to|maximum of|≦|=<|<=|=\s*<', ' <= '),
    (r'greater than|more than|higher than|above|exceeding|in excess of', ' > '),
    (r'lesser than|less than|lower than|below|under', ' < '),
]
COMPARATOR = r'(>=|<=|≥|≤|>|<)'
NUMBER = r'(\d{1,3}(?:,\d{3})+(?![\d.])|\d+,\d{1,2}(?![\d,])|\d+(?:\.\d+)?)'


def clean(text):
    text = text or ''
    for a, b in _ESCAPES:
        text = text.replace(a, b)
    text = re.sub(r'\\([^\w\s])', r'\1', text)
    text = unicodedata.normalize('NFKC', text)
    text = text.replace('≥', ' >= ').replace('≤', ' <= ').replace('×', ' x ').replace('μ', 'u').replace('µ', 'u')
    text = re.sub(r'<\s*or\s*=|</=|=/<', ' <= ', text)
    text = re.sub(r'>\s*or\s*=|>/=|=/>', ' >= ', text)
    text = text.replace('~', '-')
    text = re.sub(r'(<=|>=)\s*to\b', r'\1', text)
    text = re.sub(r'(?<=\d)\s*\*\s*(?=10|the\b|upper|uln|unl|institut)', ' x ', text, flags=re.I)   # "1.0*10^9/L", "1.5*ULN"
    text = re.sub(r'\bgrams?\s+per\s+decilit(?:er|re)\b', 'g/dL', text, flags=re.I)
    text = re.sub(r'\bgrams?\s*/\s*(?=d?L\b)', 'g/', text, flags=re.I)
    text = re.sub(r'\bmillilit(?:er|re)s?\s+per\s+minute\b', 'mL/min', text, flags=re.I)
    text = re.sub(r'\bper\s+(?:liter|litre)\b', '/L', text, flags=re.I)
    text = re.sub(r'\bper\s+microlit(?:er|re)\b|/\s*microlit(?:er|re)', '/uL', text, flags=re.I)
    text = re.sub(r'per\s+cubic\s+millimet(?:er|re)|/\s*cubic\s+millimet(?:er|re)', '/mm3', text, flags=re.I)
    text = re.sub(r'(?<=\d)\s*\(\s*(?:<|>|<=|>=)\s*\)', ' ', text)        # "lesser than (<) 20" leaves a symbol behind
    for pattern, symbol in _WORD_COMPARATORS:
        text = re.sub(r'(?<![A-Za-z])(?:' + pattern + r')(?![A-Za-z])', symbol, text, flags=re.I)
    text = re.sub(r'\(\s*(>=|<=|>|<)\s*\)', ' ', text)                     # "(>=)" echo after a spelled-out comparator
    text = re.sub(r'(>=|<=|>|<)\s+(>=|<=|>|<)', r'\1', text)                 # doubled after the echo removal
    return text


# ---------------------------------------------------------------- sections and segments
_INCLUSION = re.compile(r'^\s*(?:[*#\-\d.)\s]*)(?:key\s+)?(?:inclusion criteria|inclusion|eligibility criteria|disease characteristics|patient characteristics|prior concurrent therapy)\b', re.I)
_EXCLUSION = re.compile(r'^\s*(?:[*#\-\d.)\s]*)(?:key\s+)?(?:exclusion criteria|exclusion|non-?inclusion criteria)\b', re.I)


def _split_inline_items(line):
    """Break '... lymphodepletion 8. Eastern ... 9. Estimated ...' (numbered items run together) into lines."""
    out, last = [], 0
    for m in re.finditer(r'\s(?=\d{1,2}[.)]\s+[A-Z])', line):
        if re.search(r'(?:<=|>=|<|>|=|x|-|to|of|and|or)\s*$', line[last:m.start()], re.I):
            continue
        out.append(line[last:m.start()])
        last = m.end()
    out.append(line[last:])
    return '\n'.join(out)


def segments(text):
    """Yield (section, segment) pairs; section is 'inclusion' or 'exclusion'."""
    section = 'inclusion'
    text = re.sub(r'\n\s*(?=(?:>=|<=|>|<)\s*\d)', ' ', clean(text))      # a value wrapped onto the next line
    for line in text.split('\n'):
        stripped = line.strip()
        if not stripped:
            continue
        if _EXCLUSION.match(stripped):
            section = 'exclusion'
        elif _INCLUSION.match(stripped):
            section = 'inclusion'
        stripped = _split_inline_items(stripped)
        for part in re.split(r'\n|;|\s•\s|(?<=[a-z\)])\.\s+(?=[A-Z])|\b(?=[A-Z][a-z]+:\s)', stripped):
            if part.strip():
                yield section, part.strip()


# ---------------------------------------------------------------- criterion keywords
KEYWORDS = {
    'kidney_function_min': r'creatinine\s+clearance|creatine\s+clearance|clearance\s+of\s+(?:serum\s+)?creatinine|\bcrcl\b|\bccr\b|\bclcr\b|\begfr\b|\bgfr\b|glomerular\s+filtration',
    'creatinine_max': r'(?:serum\s+)?creatinine(?!\s+clearance)(?!\s+concentrations)',
    'anc_min': r'absolute\s+neutrophil\s+count|absolute\s+neutrophils?|absolute\s+count\s+of\s+neutrophils|\banc\b|neutrophils?(?:\s+count)?|granulocytes?(?![\s-]*(?:macrophage|colony|stimulating))(?:\s+count)?|\bagc\b',
    'platelets_min': r'platelets?(?:\s+count)?|\bplt\b|thrombocytes?',
    'hemoglobin_min': r'ha?emoglobin|\bhgb\b|\bhb\b',
    'bilirubin_max': r'(?:total\s+|serum\s+)*bilirubin|\btbil\b',
    'ast_alt_max': r'\bast\b|\balt\b|\bsgot\b|\bsgpt\b|(?-i:\bGOT\b)|\bgpt\b|transaminases?|aminotransferases?|aspartate|alanine',
    'ecog_max': r'\becog\b|zubrod|who\s+performance|\bswog\b|performance\s+status',
}
_ANY_KEYWORD = re.compile('|'.join(f'(?P<{k}>{p})' for k, p in KEYWORDS.items()), re.I)

UNITS = {
    'kidney_function_min': [(r'ml\s*/\s*min(?:ute)?\s*/\s*1\.73|ml\s*/\s*min(?:ute)?[^0-9]{0,12}?per\s+1\.73|ml\s+per\s+min(?:ute)?\s+per\s+1\.73', 'mL/min/1.73 m2'),
                            (r'ml\s*/\s*min(?:ute)?|ml\s+per\s+min(?:ute)?|milliliters?\s+per\s+minute|cc\s*/\s*min', 'mL/min')],
    'creatinine_max': [(r'(?:x|times|-?\s*fold)\s*(?:of\s+)?(?:the\s+)?(?:institutional\s+|institution\s+|local\s+|laboratory\s+)?(?:uln|unl|upper\s+(?:limits?\s+(?:of\s+)?)?(?:the\s+)?(?:normal|reference)|upper\s+limit|normal)|uln\b|unl\b', 'x ULN'),
                       (r'mg\s*/\s*dl|mg\s+%|mg/100\s*ml', 'mg/dL'), (r'u\s*mol\s*/\s*l|umol/l|micromol', 'umol/L')],
    'anc_min': [(r'x\s*10\s*(?:\^|e|\()?\s*9\s*\)?\s*/\s*l|x\s*109\s*/\s*l|10\s*\^?\s*9\s*/\s*l|g\s*/\s*l\b|x\s*10\s*9', 'x 10^9/L'),
                (r'cells\s*/\s*(?:ul|mcl|mm\s*\^?\s*3|mm3|cu\s*mm)', 'cells/uL'),
                (r'/\s*(?:mm\s*\^?\s*3|mm3|ul|mcl|cu\.?\s*mm|cubic\s+millimet(?:er|re))|per\s+(?:mm3|ul|mcl|cubic\s+millimet(?:er|re))|\bmm3\b', '/mm3 (= /uL)')],
    'platelets_min': [(r'x\s*10\s*(?:\^|e|\()?\s*9\s*\)?\s*/\s*l|x\s*109\s*/\s*l|10\s*\^?\s*9\s*/\s*l|g\s*/\s*l\b|x\s*10\s*9', 'x 10^9/L'),
                      (r'(?:cells\s*)?/\s*(?:mm\s*\^?\s*3|mm3|ul|mcl|cu\.?\s*mm|cubic\s+millimet(?:er|re))|per\s+(?:mm3|ul|mcl|cubic\s+millimet(?:er|re))|\bmm3\b', '/mm3 (= /uL)')],
    'hemoglobin_min': [(r'g\s*/\s*dl|gm\s*/\s*dl|g\s*%|gm\s*%', 'g/dL'), (r'g\s*/\s*l\b|gm\s*/\s*l\b', 'g/L'), (r'mmol\s*/\s*l', 'mmol/L')],
    'bilirubin_max': [(r'(?:x|times|-?\s*fold)\s*(?:of\s+)?(?:the\s+)?(?:institutional\s+|institution\s+|local\s+|laboratory\s+)?(?:uln|unl|upper\s+(?:limits?\s+(?:of\s+)?)?(?:the\s+)?(?:normal|reference)|upper\s+limit|normal)|uln\b|unl\b', 'x ULN'),
                      (r'mg\s*/\s*dl|mg\s*%', 'mg/dL'), (r'u\s*mol\s*/\s*l|umol/l|micromol', 'umol/L')],
    'ast_alt_max': [(r'(?:x|times|-?\s*fold)\s*(?:of\s+)?(?:the\s+)?(?:institutional\s+|institution\s+|local\s+|laboratory\s+)?(?:uln|unl|upper\s+(?:limits?\s+(?:of\s+)?)?(?:the\s+)?(?:normal|reference)|upper\s+limit|normal)|uln\b|unl\b', 'x ULN'),
                    (r'u\s*/\s*l|iu\s*/\s*l', 'U/L')],
    'ecog_max': [],
}
_FLIP = {'>=': '<', '>': '<=', '<=': '>', '<': '>='}
_CONDITIONAL = re.compile(r'\b(?:in\s+whom|if|unless|except|exception|in\s+which\s+case|otherwise|for\s+(?:patients|subjects|participants)|in\s+(?:patients|subjects|case)|when|with\s+(?:documented|known|gilbert)|due\s+to|gilbert|attributable)\b', re.I)
_NOT_A_THRESHOLD = re.compile(r'\b(?:dose|doses|dosing|will\s+receive|reduced|reduction|grade)\b', re.I)


def _unit(ctype, after):
    for pattern, label in UNITS[ctype]:
        if re.match(r'\s*(?:' + pattern + ')', after, re.I):
            return label
    if ctype in ('creatinine_max', 'bilirubin_max', 'ast_alt_max') and re.match(r'\s*(?:x\s*)?(?:uln|unl)\b', after, re.I):
        return 'x ULN'
    return 'other'


def _number(raw):
    if re.fullmatch(r'\d+,\d{1,2}', raw):
        return raw.replace(',', '.')      # decimal comma: "0,5 x 10^9/L"
    return raw.replace(',', '')


def _values_in(ctype, window):
    """Comparator-number(-unit) hits in the window following a keyword; conditional parentheses are skipped."""
    hits = []
    for m in re.finditer(COMPARATOR + r'\s*' + NUMBER, window):
        before = window[:m.start()]
        # inside a parenthesis that opened after a conditional word -> qualifier
        opened = before.rfind('(')
        if opened > before.rfind(')') and _CONDITIONAL.search(before[opened:] + window[m.end():m.end() + 40]):
            continue
        if _CONDITIONAL.search(before[-45:]) and hits:
            continue
        if _NOT_A_THRESHOLD.search(before):
            break           # text between the keyword and the number is about doses or grades, not a threshold
        if re.match(r'\s*(?:%|percent|per\s*cent)', window[m.end():], re.I):
            continue        # "(> 30 percent) marrow infiltration" is not a count
        if re.match(r'\s*[a-z/ ]{0,12}(?:<|below|under)\s*(?:the\s+)?(?:lower\s+limit|lln)', window[m.end():], re.I):
            continue        # "> 2 g/dL < lower limit of normal" is a difference, not a threshold
        comparator = {'≥': '>=', '≤': '<='}.get(m.group(1), m.group(1))
        unit = _unit(ctype, window[m.end():m.end() + 40])
        hits.append({'comparator': comparator, 'value': _number(m.group(2)), 'unit': unit})
    return hits


_D = r'(?<![\d.])([0-4])(?!\.?\d|\s*%|\s*(?:years|months|weeks|days))'


_ULN = r'(?:the\s+)?(?:institutional\s+|local\s+|laboratory\s+)?(?:uln|unl|upper\s+limits?\s+of\s+(?:the\s+)?normal(?:\s+range)?)'


def _uln_only(ctype, window):
    """'<= ULN' or 'within normal limits' with no multiplier: 1 x ULN (guide, common situations)."""
    if ctype not in ('creatinine_max', 'bilirubin_max', 'ast_alt_max'):
        return []
    head = window[:60]
    m = re.match(r'^[^0-9<>]{0,30}?(<=|<)\s*' + _ULN, head, re.I)
    if m:
        return [{'comparator': m.group(1), 'value': '1', 'unit': 'x ULN'}]
    if re.match(r'^[^0-9<>]{0,30}?\b(?:within|in)\s+(?:the\s+)?(?:institutional\s+|local\s+)?normal\s+(?:limits|range)', head, re.I):
        return [{'comparator': '<=', 'value': '1', 'unit': 'x ULN'}]
    return []


EQUATIONS = [(r'cockcroft|cockroft|crockcroft|cockgroft|cock-croft|\bc-g\b|gault', 'cockcroft_gault'), (r'\bmdrd\b|modification\s+of\s+diet', 'mdrd'),
             (r'ckd[\s-]*epi|cki-epi|chronic\s+kidney\s+disease\s+epidemiology', 'ckd_epi'),
             (r'24[\s-]*h(?:ou)?r?s?\.?\s+urine|urine\s+collection|measured', 'measured')]


def equation(segment):
    """The estimating method named in the clause; several or none -> 'not_stated'."""
    named = {label for pattern, label in EQUATIONS if re.search(pattern, segment, re.I)}
    return named.pop() if len(named) == 1 else 'not_stated'


def _ecog(window):
    """ECOG maximum from the text after the keyword: '<= 2', '0-2', '0 to 2', '0, 1 or 2', '2 or less', '> 2'."""
    window = window[:80]
    patterns = [
        (r'^[^0-9<>]{0,40}?(<=|<)\s*' + _D, lambda m: m.group(2) if m.group(1) == '<=' else str(int(m.group(2)) - 1)),
        (r'^[^0-9<>]{0,40}?' + _D + r'\s*(?:-|–|to|through)\s*' + _D, lambda m: m.group(2)),
        (r'^[^0-9<>]{0,40}?' + _D + r'(?:\s*,\s*[0-4](?![\d.]))*\s*,?\s*(?:or|and)\s*' + _D, lambda m: m.group(2)),
        (r'^[^0-9<>]{0,40}?' + _D + r'(?:\s*,\s*[0-4](?![\d.]))+', lambda m: re.findall(r'[0-4]', m.group(0))[-1]),
        (r'^[^0-9<>]{0,40}?' + _D + r'\s*or\s+(?:less|lower|below|better)', lambda m: m.group(1)),
    ]
    for pattern, value in patterns:
        m = re.search(pattern, window, re.I)
        if m:
            if pattern is patterns[1][0] and int(m.group(1)) >= 2:
                return []     # "3-4" describes a group (often an exception), not a maximum
            return [{'comparator': '<=', 'value': value(m), 'unit': 'score'}]
    m = re.search(r'^[^0-9<>]{0,40}?(>=|>)\s*' + _D, window)
    if m:      # "ECOG > 2" in an exclusion section; the caller flips it, and drops it in an inclusion section
        return [{'comparator': m.group(1), 'value': m.group(2), 'unit': 'score'}]
    return []


_CONNECTOR = re.compile(r'^[\s,/()]*(?:and\s*/\s*or|or|and|&|/|,)?[\s,/()]*(?:serum\s+|the\s+)?$', re.I)


def _mention_hits(ctype, m, seg, window):
    """Values for one keyword mention, before section flipping; [] when the mention is a qualifier or not a threshold."""
    if ctype == 'bilirubin_max' and re.search(r'\b(?:direct|conjugated|indirect)\b', seg[max(0, m.start() - 25):m.end()], re.I):
        return None             # direct bilirubin is not total bilirubin (and must not borrow a neighbour's value)
    if re.search(r'\b(?:if|unless|except)\b', seg[max(0, m.start() - 30):m.start()], re.I):
        return None             # "If there is a platelet count of >= 50 after a transfusion ..."
    if ctype == 'ecog_max':
        lead = window[:re.search(r'\d|$', window).start()]
        context = seg[max(0, m.start() - 25):m.start()] + m.group() + lead
        if re.search(r'karnofsky|lansky|\bkps\b', context, re.I) and not re.search(r'ecog|zubrod|who|swog', context, re.I):
            return None
        if _CONDITIONAL.search(seg[max(0, m.start() - 30):m.start()] + lead) or re.search(r'solely|exception', lead, re.I):
            return None
        return _ecog(window)
    return _values_in(ctype, window)[:1] or _uln_only(ctype, window)


def extract(text):
    """Extract the eight criterion types from one trial's criteria text."""
    found = {k: [] for k in KEYWORDS}
    kept_types = set()
    for section, seg in segments(text):
        matches = list(_ANY_KEYWORD.finditer(seg))
        mentions = []
        for i, m in enumerate(matches):
            ctype = m.lastgroup
            if i + 1 < len(matches) and matches[i + 1].lastgroup == ctype and not re.search(r'\d', seg[m.end():matches[i + 1].start()]):
                continue            # "Eastern Cooperative Oncology Group (ECOG) performance status": read after the last mention
            following = [n for n in matches[i + 1:] if n.lastgroup != ctype]
            end = following[0].start() if following else len(seg)
            window = seg[m.end():end]
            mentions.append({'ctype': ctype, 'm': m, 'window': window, 'end': end, 'hits': _mention_hits(ctype, m, seg, window)})
        # "bilirubin or AST > 3 x ULN", "ALT/AST <= 2.5 x ULN": a mention joined to the next by and/or takes its value
        for j in range(len(mentions) - 2, -1, -1):
            here, nxt = mentions[j], mentions[j + 1]
            if here['hits'] == [] and nxt['hits'] and here['ctype'] != 'ecog_max' and nxt['ctype'] != 'ecog_max' \
                    and _CONNECTOR.match(here['window']) and all(_unit_fits(here['ctype'], h['unit']) for h in nxt['hits']):
                here['hits'] = [dict(h) for h in nxt['hits']]
        kept_here = {}
        negated = section == 'exclusion' or (section == 'inclusion' and re.match(r'^[\W\d]*(?:no|absence\s+of|without)\b', seg, re.I))
        for mention in mentions:
            ctype, m, window, hits = mention['ctype'], mention['m'], mention['window'], mention['hits'] or []
            if not hits:
                continue
            if ctype in kept_here and ctype != 'ast_alt_max':
                continue            # a second mention in the same clause restates or qualifies the first
            if ctype in kept_here and _CONDITIONAL.search(seg[kept_here[ctype]:m.start()] + window[:80]):
                continue
            if ctype in kept_types and ctype not in kept_here and _CONDITIONAL.search(seg[max(0, m.start() - 60):m.start()] + window[:120]):
                continue            # a later, conditional value for a measure already given (marrow-involvement exceptions)
            for h in hits:
                comp = _FLIP[h['comparator']] if negated else h['comparator']
                if ctype.endswith('_min') and comp in ('<', '<='):
                    continue        # an upper bound is not a minimum (a disease definition, a range, a dose)
                if ctype.endswith('_max') and comp in ('>', '>='):
                    continue
                value = {'comparator': comp, 'value': h['value'], 'unit': h['unit'], 'section': section, 'segment': seg}
                if ctype == 'kidney_function_min':
                    value['equation'] = equation(seg)
                found[ctype].append(value)
                kept_here.setdefault(ctype, m.end())
                kept_types.add(ctype)
    result = {}
    for ctype, values in found.items():
        distinct, seen = [], set()
        for v in values:
            key = (v['comparator'], canonical(ctype, v['value'], v['unit']))
            if key not in seen:
                seen.add(key)
                distinct.append(v)
        status = 'not_stated' if not distinct else 'stated' if len(distinct) == 1 else 'multiple'
        result[ctype] = {'status': status, 'values': distinct[:3]}
    return result


def _unit_fits(ctype, unit):
    return ctype == 'ecog_max' or unit == 'other' or any(label == unit for _, label in UNITS[ctype]) or \
        (unit == 'x ULN' and ctype in ('creatinine_max', 'bilirubin_max', 'ast_alt_max'))


def canonical(ctype, value, unit):
    """Exact equivalences allowed by the plan, for de-duplication and scoring."""
    v = float(value)
    if ctype in ('anc_min', 'platelets_min'):
        if unit == 'x 10^9/L':
            return ('per_uL', round(v * 1000, 6))
        if unit in ('/mm3 (= /uL)', 'cells/uL'):
            return ('per_uL', round(v, 6))
    if ctype == 'creatinine_max':
        if unit == 'umol/L':
            return ('mg/dL', round(v / 88.42, 2))
        if unit == 'mg/dL':
            return ('mg/dL', round(v, 2))
    if ctype == 'bilirubin_max':
        if unit == 'umol/L':
            return ('mg/dL', round(v / 17.1, 2))
        if unit == 'mg/dL':
            return ('mg/dL', round(v, 2))
    if ctype == 'hemoglobin_min':
        if unit == 'g/L':
            return ('g/dL', round(v / 10, 3))
        if unit == 'g/dL':
            return ('g/dL', round(v, 3))
    return (unit, round(v, 6))

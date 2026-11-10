"""Check that every quote in a pinned extract appears in its source document (AI review of 10 November 2026, F10, F28).

Usage, from the repository root:
    python3 scripts/check_source_quotes.py EXTRACT.json SOURCE.(pdf|docx|txt) [--sha256 EXPECTED]

Text is taken with `pdftotext` for a PDF (layout, default and raw text, all searched), from the document XML for a .docx (paragraphs and table cells), or read
as UTF-8 for a text file. Whitespace is collapsed on both sides before matching; nothing else is normalised. Every string
under a key ending in "quote" (or in a list under "quotes") is checked. Prints one line per quote and exits non-zero if
any quote is missing or the source's SHA-256 differs from --sha256. Sources stay in supplemental-information/ (not in git),
so this runs where the source is, not in CI.
"""
import argparse
import hashlib
import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path


def source_text(path):
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == '.pdf':
        # Both the column-preserving layout text (tables) and the reading-order text (two-column prose) are searched.
        run = lambda *flags: subprocess.run(['pdftotext', *flags, str(path), '-'], check=True, capture_output=True, text=True).stdout
        return run('-layout') + '\n' + run() + '\n' + run('-raw')
    if suffix == '.docx':
        with zipfile.ZipFile(path) as z:
            xml = z.read('word/document.xml').decode('utf-8')
        xml = re.sub(r'</w:p>|</w:tc>', '\n', xml)
        xml = re.sub(r'<w:tab/>', '\t', xml)
        text = re.sub(r'<[^>]+>', '', xml)
        return (text.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
                .replace('&quot;', '"').replace('&apos;', "'"))
    return path.read_text(encoding='utf-8')


def collapse(text):
    return re.sub(r'\s+', ' ', text).strip()


def quotes(node, pointer=''):
    if isinstance(node, dict):
        for key, value in node.items():
            here = f'{pointer}/{key}'
            if key.endswith('quote') and isinstance(value, str):
                yield here, value
            elif key == 'quotes' and isinstance(value, list):
                for i, q in enumerate(value):
                    if isinstance(q, str):
                        yield f'{here}/{i}', q
            else:
                yield from quotes(value, here)
    elif isinstance(node, list):
        for i, value in enumerate(node):
            yield from quotes(value, f'{pointer}/{i}')


def check(extract_path, source_path, expected_sha256=None):
    digest = hashlib.sha256(Path(source_path).read_bytes()).hexdigest()
    text = collapse(source_text(source_path))
    results = [(pointer, collapse(q) in text) for pointer, q in quotes(json.loads(Path(extract_path).read_text()))]
    return {'source_sha256': digest, 'sha256_matches': expected_sha256 in (None, digest), 'results': results}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('extract')
    parser.add_argument('source')
    parser.add_argument('--sha256')
    args = parser.parse_args(argv)
    out = check(args.extract, args.source, args.sha256)
    print(f"source SHA-256 {out['source_sha256']}" + ('' if out['sha256_matches'] else f' (expected {args.sha256})'))
    for pointer, found in out['results']:
        print(('found   ' if found else 'MISSING ') + pointer)
    ok = out['sha256_matches'] and out['results'] and all(found for _, found in out['results'])
    print(f"{sum(f for _, f in out['results'])} of {len(out['results'])} quotes found")
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())

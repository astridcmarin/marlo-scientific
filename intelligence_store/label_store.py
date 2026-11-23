"""Label tables for the ingestion pilot (decision 0009): a manifest of DailyMed files, and insert-only tables.

The pilot builds the three tables of decision 0009 in a standalone SQLite file with the same columns the app
migration will add if the pilot passes, so that the build is rebuildable and measurable without the app
database. Rows are insert-only: triggers refuse updates and deletes.
"""
import hashlib
import json
import sqlite3
from pathlib import Path

from .spl_labels import RX_DOCUMENT_CODE, SplError, read_label, xml_from_zip

MANIFEST_SCHEMA = 'dailymed-label-manifest-v1'
SCHEMA = """
CREATE TABLE label_document (
  set_id TEXT NOT NULL, version INTEGER NOT NULL, manifest_sha256 TEXT NOT NULL,
  document_id TEXT, document_type_code TEXT, effective_time TEXT, title TEXT,
  marketing_categories TEXT NOT NULL, category_class TEXT NOT NULL, application_numbers TEXT NOT NULL,
  xml_sha256 TEXT NOT NULL, method_version TEXT NOT NULL, PRIMARY KEY (set_id, version, method_version));
CREATE TABLE label_section (
  set_id TEXT NOT NULL, version INTEGER NOT NULL, method_version TEXT NOT NULL, ord INTEGER NOT NULL,
  parent_ord INTEGER, code TEXT, code_system TEXT, code_name TEXT, heading TEXT, text TEXT NOT NULL,
  text_sha256 TEXT NOT NULL, excerpts_skipped INTEGER NOT NULL,
  PRIMARY KEY (set_id, version, method_version, ord));
CREATE TABLE label_ingredient (
  set_id TEXT NOT NULL, version INTEGER NOT NULL, method_version TEXT NOT NULL, unii TEXT NOT NULL, name TEXT,
  PRIMARY KEY (set_id, version, method_version, unii));
"""
TABLES = ('label_document', 'label_section', 'label_ingredient')
TRIGGERS = ''.join(
    f"CREATE TRIGGER {t}_no_{op} BEFORE {op.upper()} ON {t} BEGIN SELECT RAISE(ABORT, '{t} is insert-only'); END;"
    for t in TABLES for op in ('update', 'delete'))


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def build_manifest(zip_paths, created_on, purpose):
    """One manifest entry per label zip. Labels that are not human prescription labels, or that cannot be read,
    are listed under 'refused' with the reason, never silently dropped."""
    labels, refused = [], []
    for path in sorted(Path(p) for p in zip_paths):
        raw = path.read_bytes()
        try:
            member, xml = xml_from_zip(raw)
            lab = read_label(xml)
        except (SplError, OSError, ValueError) as exc:
            refused.append({'zip_name': path.name, 'zip_sha256': hashlib.sha256(raw).hexdigest(), 'reason': str(exc)})
            continue
        if lab['document_type_code'] != RX_DOCUMENT_CODE:
            refused.append({'zip_name': path.name, 'zip_sha256': hashlib.sha256(raw).hexdigest(),
                            'reason': f'document type {lab["document_type_code"]}, not {RX_DOCUMENT_CODE}'})
            continue
        labels.append({'set_id': lab['set_id'], 'version': lab['version'], 'effective_time': lab['effective_time'],
                       'title': lab['title'], 'marketing_categories': lab['marketing_categories'],
                       'category_class': lab['category_class'], 'application_numbers': lab['application_numbers'],
                       'ingredients': lab['ingredients'], 'zip_name': path.name,
                       'zip_sha256': hashlib.sha256(raw).hexdigest(), 'xml_member': member,
                       'xml_sha256': lab['xml_sha256'], 'method_version': lab['method_version']})
    keys = [(l['set_id'], l['version']) for l in labels]
    if len(keys) != len(set(keys)):
        raise ValueError('The same label version appears twice.')
    return {'schema_version': MANIFEST_SCHEMA, 'created_on': created_on, 'purpose': purpose,
            'source': 'DailyMed structured product labels, per-label zip files',
            'labels': sorted(labels, key=lambda l: (l['set_id'], l['version'])), 'refused': refused}


def create(db_path):
    con = sqlite3.connect(db_path)
    con.executescript(SCHEMA + TRIGGERS)
    return con


def build(db_path, manifest_raw, zip_dir):
    """Build the tables from a manifest (its exact bytes) and the zip files it names. Each zip and XML is checked
    against the manifest's checksums before anything is inserted for it."""
    if Path(db_path).exists():
        raise FileExistsError(f'{db_path} exists; a build never writes into an existing database.')
    manifest = json.loads(manifest_raw)
    if manifest.get('schema_version') != MANIFEST_SCHEMA:
        raise ValueError('Unknown manifest schema.')
    msha = hashlib.sha256(manifest_raw).hexdigest()
    con = create(db_path)
    with con:
        for entry in manifest['labels']:
            raw = (Path(zip_dir) / entry['zip_name']).read_bytes()
            if hashlib.sha256(raw).hexdigest() != entry['zip_sha256']:
                raise ValueError(f'{entry["zip_name"]} does not match the manifest.')
            _, xml = xml_from_zip(raw)
            lab = read_label(xml)
            if lab['xml_sha256'] != entry['xml_sha256'] or (lab['set_id'], lab['version']) != (entry['set_id'], entry['version']):
                raise ValueError(f'{entry["zip_name"]}: XML does not match the manifest.')
            key = (lab['set_id'], lab['version'], lab['method_version'])
            con.execute('INSERT INTO label_document VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                        key[:2] + (msha, lab['document_id'], lab['document_type_code'], lab['effective_time'],
                                   lab['title'], json.dumps(lab['marketing_categories']), lab['category_class'],
                                   json.dumps(lab['application_numbers']), lab['xml_sha256'], key[2]))
            for s in lab['sections']:
                con.execute('INSERT INTO label_section VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                            key + (s['ord'], s['parent_ord'], s['code'], s['code_system'], s['code_name'],
                                   s['heading'], s['text'], s['text_sha256'], s['excerpts_skipped']))
            for i in lab['ingredients']:
                con.execute('INSERT INTO label_ingredient VALUES (?,?,?,?,?)', key + (i['unii'], i['name']))
    return con


def content_digest(con):
    """SHA-256 over every row of the three tables in key order, excluding nothing; equal digests mean equal
    content. The manifest checksum column is included, so two builds compare only from the same manifest."""
    h = hashlib.sha256()
    for table, order in (('label_document', 'set_id, version, method_version'),
                         ('label_section', 'set_id, version, method_version, ord'),
                         ('label_ingredient', 'set_id, version, method_version, unii')):
        for row in con.execute(f'SELECT * FROM {table} ORDER BY {order}'):
            h.update(json.dumps([table, list(row)], ensure_ascii=False).encode('utf-8'))
    return h.hexdigest()


def measures(con, db_path, manifest_raw):
    n_docs = con.execute('SELECT COUNT(*) FROM label_document').fetchone()[0]
    n_secs = con.execute('SELECT COUNT(*) FROM label_section').fetchone()[0]
    text_bytes = con.execute('SELECT COALESCE(SUM(LENGTH(CAST(text AS BLOB))), 0) FROM label_section').fetchone()[0]
    skipped = con.execute('SELECT COALESCE(SUM(excerpts_skipped), 0) FROM label_section').fetchone()[0]
    empty = con.execute("SELECT COUNT(*) FROM label_section WHERE text = ''").fetchone()[0]
    con.commit()
    size = Path(db_path).stat().st_size
    return {'labels': n_docs, 'sections': n_secs, 'sections_without_text': empty, 'excerpts_skipped': skipped,
            'section_text_bytes': text_bytes, 'database_bytes': size, 'manifest_bytes': len(manifest_raw),
            'per_label': {k: (v / n_docs if n_docs else None) for k, v in
                          (('sections', n_secs), ('database_bytes', size), ('manifest_bytes', len(manifest_raw)))}}

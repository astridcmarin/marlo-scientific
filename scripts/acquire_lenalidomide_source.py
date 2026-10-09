#!/usr/bin/env python3
"""Acquire or import a PDF source into a separate, immutable local evidence archive."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
from urllib.request import Request,urlopen

MAX_BYTES=10*1024*1024
SOURCES={
    'supplement':{
        'url':'https://pmc.ncbi.nlm.nih.gov/articles/instance/4070318/bin/NIHMS583352-supplement-Supplement.pdf',
        'description':'PMC-linked Lu et al. supplement; previously blocked during automated access.'},
    'main':{
        'url':'https://ptacts.uspto.gov/ptacts/public-informations/petitions/1548175/download-documents?artifactId=RL29MY_GXU2oUPRmcHaWSVw8Og_tdgblLAeayPI-f7eTf4ln-ZaNOTI',
        'description':'Public USPTO-hosted copy of the primary paper; includes adjacent article material.'}}


def validate_pdf_bytes(raw):
    if not raw or len(raw)>MAX_BYTES:raise ValueError('Source is empty or exceeds 10 MiB.')
    if not raw.startswith(b'%PDF-') or b'%%EOF' not in raw[-2048:]:
        raise ValueError('Response is not a supported PDF file. It may be an access/error page; no archive was created.')
    # Signature checks identify a candidate PDF only, not safe rendering,
    # correct scientific identity, completeness or legibility.


def acquire_bytes(*,source,file=None,fetch=False):
    if source not in SOURCES:raise ValueError('Unsupported source role.')
    if (file is None)==(not fetch):raise ValueError('Choose exactly one of --fetch or --file.')
    if file is not None:
        with Path(file).open('rb') as stream:raw=stream.read(MAX_BYTES+1)
        metadata={'acquisition_method':'manual_file_import','original_filename':Path(file).name,
            'requested_url':None,'returned_url':None,'reported_content_type':None,
            'source_identity_status':'user_declared_role_not_verified'}
    else:
        url=SOURCES[source]['url']
        request=Request(url,headers={'User-Agent':'ClinicalTrialsIntelligence-EvidenceArchive/1.0',
            'Accept':'application/pdf'})
        with urlopen(request,timeout=30) as response:
            raw=response.read(MAX_BYTES+1)
            metadata={'acquisition_method':'fixed_public_url_fetch','original_filename':None,
                'requested_url':url,'returned_url':response.geturl(),
                'reported_content_type':response.headers.get('Content-Type'),
                'source_identity_status':'download_location_recorded_contents_not_verified'}
    validate_pdf_bytes(raw)
    return raw,metadata


def archive_source(*,raw,source,metadata,output_dir):
    if source not in SOURCES:raise ValueError('Unsupported source role.')
    validate_pdf_bytes(raw)
    digest=hashlib.sha256(raw).hexdigest()
    root=Path(output_dir).resolve()/source
    destination=root/digest
    # Files are grouped by declared role and exact bytes; never overwrite an archive.
    if destination.exists():
        stored=(destination/'source.pdf').read_bytes()
        manifest=json.loads((destination/'manifest.json').read_text(encoding='utf-8'))
        if stored!=raw or manifest.get('source_sha256')!=digest or manifest.get('declared_source_role')!=source:
            raise ValueError('Existing archive is incomplete or inconsistent; no files were overwritten.')
        return {'status':'already_archived','archive_directory':str(destination),'manifest':manifest}
    manifest={'schema_version':'local-pharmacology-source-archive-v1','archive_method_version':'pdf-byte-archive-v1.0',
        'expected_paper_doi':'10.1126/science.1244917','declared_source_role':source,
        'source_role_description':SOURCES[source]['description'],'source_sha256':digest,'byte_count':len(raw),
        'archived_at':datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),
        'acquisition':metadata,'validation_scope':'PDF header/EOF signature and size only; no parser or scientific-content review.',
        'review_status':'not_reviewed','figure_data_extracted':False,'supplement_methods_reviewed':False,
        'clinical_prediction_validated':False,'ready_for_patient_simulation':False}
    root.mkdir(parents=True,exist_ok=True)
    temporary=Path(tempfile.mkdtemp(prefix='.pending-source-',dir=root))
    try:
        (temporary/'source.pdf').write_bytes(raw)
        (temporary/'manifest.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False,allow_nan=False)+'\n',encoding='utf-8')
        # Renaming a directory publishes both files together. An existing populated
        # archive cannot be replaced by this rename on supported POSIX systems.
        os.rename(temporary,destination)
    finally:
        if temporary.exists():shutil.rmtree(temporary)
    return {'status':'archived','archive_directory':str(destination),'manifest':manifest}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',choices=sorted(SOURCES),required=True)
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--fetch',action='store_true')
    mode.add_argument('--file',type=Path)
    parser.add_argument('--output-dir',type=Path,default=Path('instance/lenalidomide_sources'))
    args=parser.parse_args(argv)
    try:
        raw,metadata=acquire_bytes(source=args.source,file=args.file,fetch=args.fetch)
        result=archive_source(raw=raw,source=args.source,metadata=metadata,output_dir=args.output_dir)
        print(json.dumps(result,indent=2,ensure_ascii=False,allow_nan=False))
        return 0
    except (OSError,ValueError) as exc:
        print('Source acquisition failed: '+str(exc),file=sys.stderr)
        print('If automated access is blocked, download the PDF normally and rerun with --file. No source review or readiness promotion was performed.',file=sys.stderr)
        return 1


if __name__=='__main__':raise SystemExit(main())

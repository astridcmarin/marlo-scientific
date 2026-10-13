import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('source_acquisition',ROOT/'scripts/acquire_lenalidomide_source.py')
tool=importlib.util.module_from_spec(spec);spec.loader.exec_module(tool)
# Signature fixture only. Tests never claim that this is a renderable paper.
PDF=b'%PDF-1.4\nsynthetic signature-test fixture\n%%EOF\n'


class SourceAcquisitionTests(unittest.TestCase):
    def test_manual_archive_hash_unreviewed_status_and_idempotence(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'download.pdf';source.write_bytes(PDF)
            with patch.object(tool,'urlopen',side_effect=AssertionError('Manual import must not fetch')):
                raw,metadata=tool.acquire_bytes(source='supplement',file=source)
            result=tool.archive_source(raw=raw,source='supplement',metadata=metadata,output_dir=root/'archives')
            destination=Path(result['archive_directory'])
            before={p.name:p.read_bytes() for p in destination.iterdir()}
            self.assertEqual(result['manifest']['source_sha256'],hashlib.sha256(PDF).hexdigest())
            self.assertEqual(result['manifest']['review_status'],'not_reviewed')
            self.assertFalse(result['manifest']['supplement_methods_reviewed'])
            self.assertFalse(result['manifest']['ready_for_patient_simulation'])
            repeated=tool.archive_source(raw=raw,source='supplement',metadata=metadata,output_dir=root/'archives')
            self.assertEqual(repeated['status'],'already_archived')
            self.assertEqual(before,{p.name:p.read_bytes() for p in destination.iterdir()})

    def test_error_html_and_oversized_files_create_no_archive(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)/'archives'
            for raw in [b'<html>Access blocked</html>',b'',b'%PDF-no-eof',b'x'*(tool.MAX_BYTES+1)]:
                with self.assertRaises(ValueError):tool.archive_source(raw=raw,source='main',metadata={},output_dir=root)
            self.assertFalse(root.exists())

    def test_inconsistent_existing_archive_is_not_repaired_or_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            result=tool.archive_source(raw=PDF,source='main',metadata={},output_dir=folder)
            path=Path(result['archive_directory'])/'source.pdf';path.write_bytes(b'changed')
            with self.assertRaises(ValueError):tool.archive_source(raw=PDF,source='main',metadata={},output_dir=folder)
            self.assertEqual(path.read_bytes(),b'changed')

    def test_fetch_records_request_response_without_treating_pdf_as_reviewed(self):
        class Response:
            headers={'Content-Type':'application/pdf'}
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read(self,limit):return PDF
            def geturl(self):return 'https://example.org/public-source.pdf'
        with patch.object(tool,'urlopen',return_value=Response()) as fetch:
            raw,metadata=tool.acquire_bytes(source='main',fetch=True)
        self.assertEqual(raw,PDF)
        self.assertEqual(fetch.call_args.kwargs['timeout'],30)
        self.assertEqual(metadata['requested_url'],tool.SOURCES['main']['url'])
        self.assertEqual(metadata['returned_url'],'https://example.org/public-source.pdf')
        self.assertIn('not_verified',metadata['source_identity_status'])

    def test_write_failure_leaves_no_published_or_pending_archive(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(tool.os,'rename',side_effect=OSError('Simulated write failure')):
                with self.assertRaises(OSError):tool.archive_source(raw=PDF,source='main',metadata={},output_dir=folder)
            self.assertEqual(list((Path(folder)/'main').iterdir()),[])


if __name__=='__main__':unittest.main()

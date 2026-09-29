import importlib.util
import json
from pathlib import Path
from subprocess import CompletedProcess
import unittest

spec = importlib.util.spec_from_file_location('digest', Path(__file__).resolve().parents[1] / 'scripts/image-digest.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class RegistryTests(unittest.TestCase):
    reference = 'ghcr.io/example/image:v8.0.3-0.1.3'

    def inspect(self, stdout='', stderr='', code=0):
        return module.image_digest(self.reference, run=lambda *a, **kw: CompletedProcess(a, code, stdout, stderr))

    def test_existing_version_returns_digest(self):
        digest = 'sha256:' + 'a' * 64
        self.assertEqual(self.inspect(json.dumps({'digest': digest})), digest)

    def test_explicit_absence(self):
        self.assertEqual(self.inspect(stderr=f'ERROR: {self.reference}: not found\n', code=1), '')

    def test_registry_errors_never_allow_overwrite(self):
        for error in ['401 Unauthorized', '403 Forbidden', 'timeout', '500 Internal Server Error',
                      'ERROR: hostname not found', f'ERROR: {self.reference}: not found\naccess denied']:
            with self.subTest(error=error), self.assertRaises(RuntimeError):
                self.inspect(stderr=error, code=1)

    def test_invalid_manifest_fails_closed(self):
        for value in ['{}', 'not json', '{"digest":"bad"}']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.inspect(stdout=value)

    def test_complete_rc_publication_is_idempotent(self):
        self.assertFalse(module.publication_needed('image', 'version', lambda ref: 'sha256:' + 'a' * 64))

    def test_missing_version_or_interrupted_alias_promotion_is_retried(self):
        digest = 'sha256:' + 'a' * 64
        for tag in ['version', 'rc', 'latest']:
            for stale in ['', 'sha256:' + 'b' * 64]:
                with self.subTest(tag=tag, stale=stale):
                    state = dict.fromkeys(['image:version', 'image:rc', 'image:latest'], digest)
                    state['image:' + tag] = stale
                    self.assertTrue(module.publication_needed('image', 'version', state.__getitem__))

    def test_missing_version_does_not_hide_alias_lookup_failure(self):
        def inspect(reference):
            if reference == 'image:version':
                return ''
            raise RuntimeError('registry unavailable')
        with self.assertRaisesRegex(RuntimeError, 'registry unavailable'):
            module.publication_needed('image', 'version', inspect)

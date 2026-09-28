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

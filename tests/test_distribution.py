"""Offline checks of credential/config lifecycle. No Google account involved."""
import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('init_config', ROOT / 'scripts/init-config.py')
init_config = importlib.util.module_from_spec(spec)
spec.loader.exec_module(init_config)


class DistributionTests(unittest.TestCase):
    def test_key_survives_reinitialization_and_manual_edit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_config.initialize(root, ROOT / 'config.example.yaml')
            config = root / 'config.yaml'
            original = config.read_text()
            self.assertNotIn('__GENERATED_CLIENT_KEY__', original)
            self.assertEqual(config.stat().st_mode & 0o777, 0o600)
            config.write_text(original + '\n# custom setting\n')
            init_config.initialize(root, ROOT / 'config.example.yaml')
            self.assertEqual(config.read_text(), original + '\n# custom setting\n')

    def test_bad_template_never_creates_partial_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            template = root / 'template'
            template.write_text('missing marker')
            with self.assertRaises(ValueError):
                init_config.initialize(root / 'config', template)
            self.assertFalse((root / 'config/config.yaml').exists())

    def test_reuses_existing_agy_when_install_disabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            binary = Path(tmp) / '.local/bin/agy'
            binary.parent.mkdir(parents=True)
            binary.write_text('#!/bin/sh\nexit 0\n')
            binary.chmod(0o700)
            before = binary.read_bytes()
            result = subprocess.run(['bash', str(ROOT / 'scripts/bootstrap-agy.sh')],
                env={**os.environ, 'HOME': tmp, 'AGY_AUTO_INSTALL': 'false'}, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(binary.read_bytes(), before)

    def test_missing_agy_does_not_silently_start(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run(['bash', str(ROOT / 'scripts/bootstrap-agy.sh')],
                env={**os.environ, 'HOME': tmp, 'AGY_AUTO_INSTALL': 'false'}, capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(b'agy missing', result.stderr)


if __name__ == '__main__':
    unittest.main()

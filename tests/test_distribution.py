"""Offline checks of credential/config lifecycle. No Google account involved."""
import importlib.util
from pathlib import Path
import tempfile
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
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



if __name__ == '__main__':
    unittest.main()

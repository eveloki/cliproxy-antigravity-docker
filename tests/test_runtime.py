import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import runtime_config as runtime
spec = importlib.util.spec_from_file_location('prepare_plugins', ROOT / 'scripts/prepare-plugins.py')
plugins = importlib.util.module_from_spec(spec)
spec.loader.exec_module(plugins)


class RuntimeTests(unittest.TestCase):
    def test_legacy_and_v8_precedence(self):
        cfg = {'port': 9000, 'host': '0.0.0.0', 'api-keys': ['legacy']}
        self.assertEqual(runtime.endpoint(cfg), 'http://127.0.0.1:9000')
        self.assertEqual(runtime.client_key(cfg), 'legacy')
        cfg.update(server={'host': '::', 'port': 9001}, access={'api-keys': ['new']})
        self.assertEqual(runtime.endpoint(cfg), 'http://[::1]:9001')
        self.assertEqual(runtime.client_key(cfg), 'new')
        cfg['access']['api-keys'] = []
        self.assertEqual(runtime.client_key(cfg), '')

    def test_explicit_config_beats_environment_and_state(self):
        with patch.dict(os.environ, {'CPA_CONFIG': '/config/other.yaml'}):
            for args in [['-config', '/chosen.yaml'], ['--config=/chosen.yaml']]:
                self.assertEqual(runtime.config_path(args), Path('/chosen.yaml'))
            self.assertEqual(runtime.config_path(use_state=False), Path('/config/other.yaml'))
        with self.assertRaises(ValueError):
            runtime.config_path(['-config'])

    def test_managed_plugin_upgrade_preserves_other_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src, dest = root / 'cliproxy-antigravity.so', root / 'plugins'
            src.write_bytes(b'first')
            plugins.seed(src, dest)
            other = dest / 'other-plugin.so'
            other.write_bytes(b'user plugin')
            src.write_bytes(b'second')
            plugins.seed(src, dest)
            self.assertEqual((dest / src.name).read_bytes(), b'second')
            self.assertEqual(other.read_bytes(), b'user plugin')
            (dest / src.name).write_bytes(b'user replacement')
            src.write_bytes(b'third')
            plugins.seed(src, dest)
            self.assertEqual((dest / src.name).read_bytes(), b'user replacement')

    def test_unknown_existing_plugin_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src, dest = root / 'cliproxy-antigravity.so', root / 'plugins'
            src.write_bytes(b'ours')
            dest.mkdir()
            target = dest / src.name
            target.write_bytes(b'existing')
            plugins.seed(src, dest)
            self.assertEqual(target.read_bytes(), b'existing')

    def test_disabled_or_absent_plugin_does_not_write_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg = root / 'config.yaml'
            cfg.write_text('plugins:\n  enabled: true\n  dir: ' + str(root / 'plugins') + '\n')
            plugins.prepare(cfg)
            self.assertFalse((root / 'plugins').exists())


if __name__ == '__main__':
    unittest.main()

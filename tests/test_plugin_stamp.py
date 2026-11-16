import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('stamp', Path(__file__).resolve().parents[1] / 'compat/stamp-version.py')
stamp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stamp)


class PluginStampTests(unittest.TestCase):
    def test_future_release_keeps_exact_custom_identity(self):
        for version in ('0.3.1', '0.3.2'):
            with tempfile.TemporaryDirectory() as tmp:
                p = Path(tmp) / 'plugin.go'
                p.write_text('const pluginVersion = "' + version + '"\n')
                stamp.stamp(p, 'v' + version)
                self.assertIn('"' + version + '+dist1"', p.read_text())

    def test_mismatch_or_ambiguous_source_fails_without_writing(self):
        for content in ('const pluginVersion = "0.1.3"', 'nothing',
                        'pluginVersion="0.3.1"\npluginVersion="0.3.1"'):
            with tempfile.TemporaryDirectory() as tmp:
                p = Path(tmp) / 'plugin.go'; p.write_text(content)
                with self.assertRaises(ValueError): stamp.stamp(p, 'v0.3.1')
                self.assertEqual(p.read_text(), content)

    def test_unstable_input_is_rejected(self):
        with self.assertRaises(ValueError): stamp.stamp('unused', '0.3.1-rc1')

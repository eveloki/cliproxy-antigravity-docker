import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('upgrade_state', Path(__file__).with_name('upgrade-state.py'))
state = importlib.util.module_from_spec(spec)
spec.loader.exec_module(state)


class UpgradeSnapshotTests(unittest.TestCase):
    def test_reserialization_allowed_but_field_changes_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'upgrade-codex.json'
            data = {'type': 'codex', 'disabled': True, 'access_token': 'synthetic'}
            p.write_text(json.dumps(data, indent=2) + '\n')
            p.chmod(0o600)
            before = state.fingerprint(p)
            p.write_text(json.dumps(data, sort_keys=True, separators=(',', ':')))
            self.assertEqual(before, state.fingerprint(p))
            for altered in [dict(data, access_token='changed'), dict(data, disabled=False),
                            dict(data, unexpected=True), {'type': 'codex'}]:
                p.write_text(json.dumps(altered))
                self.assertNotEqual(before, state.fingerprint(p))
            p.write_text(json.dumps(data))
            p.chmod(0o644)
            self.assertNotEqual(before, state.fingerprint(p))

    def test_opaque_files_still_require_identical_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'existing.db'
            p.write_bytes(b'{"a":1}')
            before = state.fingerprint(p)
            p.write_bytes(b'{"a": 1}')
            self.assertNotEqual(before, state.fingerprint(p))

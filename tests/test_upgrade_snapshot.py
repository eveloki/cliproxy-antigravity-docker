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


class ConfigTransitionTests(unittest.TestCase):
    def test_only_new_uuid_and_serialization_change_allowed(self):
        before = {'server': {'port': 8317}, 'access': {'api-keys': ['synthetic']}, 'plugins': {'dir': '/old/plugins'}}
        after = json.loads(json.dumps(before))
        after['server']['server-id'] = '706aa936-c50a-4728-8420-a5e94c9c990b'
        state.config_identity_transition(before, after)
        self.assertNotIn('server-id', before['server'])  # Do not mutate caller snapshots.
        for field in ('key', 'port', 'plugin', 'extra'):
            changed = json.loads(json.dumps(after))
            if field == 'key': changed['access']['api-keys'] = ['rotated']
            if field == 'port': changed['server']['port'] = 9999
            if field == 'plugin': changed['plugins']['dir'] = '/different'
            if field == 'extra': changed['unexpected'] = True
            with self.assertRaises(AssertionError): state.config_identity_transition(before, changed)

    def test_invalid_missing_or_existing_identity_rejected(self):
        before = {'server': {'port': 8317}}
        for value in (None, '', 'invalid', '00000000-0000-0000-0000-000000000000', 123):
            with self.assertRaises((AssertionError, ValueError)):
                state.config_identity_transition(before, {'server': {'port': 8317, 'server-id': value}})
        with self.assertRaises(AssertionError):
            state.config_identity_transition({'server': {'server-id': 'old-id'}}, {'server': {'server-id': '706aa936-c50a-4728-8420-a5e94c9c990b'}})

    def test_accepted_config_is_pinned_across_recreation_and_rollback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); p = root / 'config.yaml'; accepted = root / 'accepted.json'
            p.write_text('# preserve comment\nserver: {port: 8317}\naccess: {api-keys: [synthetic]}\n')
            p.chmod(0o600)
            original = state.fingerprint(p)
            original.update(yaml=state.yaml.safe_load(p.read_text()), comments=state.config_comments(p.read_text()))
            p.write_text('# preserve comment\nserver: {port: 8317, server-id: 706aa936-c50a-4728-8420-a5e94c9c990b}\naccess: {api-keys: [synthetic]}\n')
            state.verify_config(p, original, 'new', accepted)
            state.verify_config(p, original, 'new', accepted)
            state.verify_config(p, original, 'old', accepted)
            p.write_text(p.read_text().replace('706aa936-c50a-4728-8420-a5e94c9c990b', '706aa936-c50a-4728-8420-a5e94c9c990c'))
            with self.assertRaises(AssertionError): state.verify_config(p, original, 'new', accepted)

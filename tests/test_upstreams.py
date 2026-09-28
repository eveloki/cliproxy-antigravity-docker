import copy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('upstreams', ROOT / 'scripts/update-upstreams.py')
upstreams = importlib.util.module_from_spec(spec)
spec.loader.exec_module(upstreams)


class UpstreamTests(unittest.TestCase):
    def setUp(self):
        self.lock = json.loads((ROOT / 'upstream-versions.json').read_text())
        self.replies = {}
        for key in upstreams.REPOSITORIES:
            entry = self.lock[key]
            repo, tag = entry['repository'], entry['version']
            self.replies[f'repos/{repo}/releases/latest'] = {'tag_name': tag, 'draft': False, 'prerelease': False}
            self.replies[f'repos/{repo}/git/ref/tags/{tag}'] = {'object': {'type': 'commit', 'sha': entry['commit']}}

    def get(self, path):
        return self.replies[path]

    def test_unchanged_is_idempotent(self):
        self.lock['packaging_revision'] = 2
        self.assertEqual(upstreams.next_lock(self.lock, self.get), self.lock)

    def test_patch_update_and_annotated_tag(self):
        self.lock['packaging_revision'] = 3
        entry = self.lock['cpa']
        major, minor, patch = upstreams.version_tuple(entry['version'])
        tag = f'v{major}.{minor}.{patch + 1}'
        repo = entry['repository']
        self.replies[f'repos/{repo}/releases/latest']['tag_name'] = tag
        self.replies[f'repos/{repo}/git/ref/tags/{tag}'] = {'object': {'type': 'tag', 'sha': 'a' * 40}}
        self.replies[f'repos/{repo}/git/tags/{"a" * 40}'] = {'object': {'type': 'commit', 'sha': 'b' * 40}}
        before = copy.deepcopy(self.lock)
        result = upstreams.next_lock(self.lock, self.get)
        self.assertEqual(result['cpa']['version'], tag)
        self.assertEqual(result['cpa']['commit'], 'b' * 40)
        self.assertEqual(result['packaging_revision'], 1)
        self.assertEqual(self.lock, before)

    def test_fixed_tag_and_packaging_revision(self):
        self.lock['cpa']['version'] = 'v8.0.3'
        self.lock['plugin']['version'] = '0.1.3'
        self.lock['packaging_revision'] = 1
        self.assertEqual(upstreams.image_tag(self.lock), 'v8.0.3-0.1.3-agy1.2.12-r1')
        self.lock['packaging_revision'] = 2
        self.assertEqual(upstreams.image_tag(self.lock), 'v8.0.3-0.1.3-agy1.2.12-r2')
        for revision in [0, -1, True, '2']:
            self.lock['packaging_revision'] = revision
            with self.assertRaises(ValueError):
                upstreams.image_tag(self.lock)

    def test_moved_tag_is_rejected(self):
        entry = self.lock['cpa']
        self.replies[f'repos/{entry["repository"]}/git/ref/tags/{entry["version"]}']['object']['sha'] = 'f' * 40
        with self.assertRaisesRegex(ValueError, 'tag moved'):
            upstreams.next_lock(self.lock, self.get)

    def test_major_upgrade_is_candidate_and_cli_stays_pinned(self):
        entry = self.lock['cpa']
        major, _, _ = upstreams.version_tuple(entry['version'])
        tag = f'v{major + 1}.0.0'
        repo = entry['repository']
        self.replies[f'repos/{repo}/releases/latest']['tag_name'] = tag
        self.replies[f'repos/{repo}/git/ref/tags/{tag}'] = {'object': {'type': 'commit', 'sha': 'c' * 40}}
        result = upstreams.next_lock(self.lock, self.get)
        self.assertEqual(result['cpa']['version'], tag)
        self.assertEqual(result['agy'], self.lock['agy'])

    def test_downgrade_is_rejected(self):
        entry = self.lock['cpa']
        self.replies[f'repos/{entry["repository"]}/releases/latest']['tag_name'] = 'v1.0.0'
        with self.assertRaisesRegex(ValueError, 'downgrade'):
            upstreams.next_lock(self.lock, self.get)

    def test_invalid_cli_pins_are_rejected(self):
        for field, value in [('sha256', 'a' * 63), ('repository', 'other/repo'),
                             ('asset', 'other.tar.gz'), ('version', '1.2.12-rc1')]:
            with self.subTest(field=field):
                lock = copy.deepcopy(self.lock)
                lock['agy'][field] = value
                with self.assertRaises(ValueError):
                    upstreams.image_tag(lock)

    def test_untrusted_versions_and_pre_releases_are_rejected(self):
        for value in ['v8.0.4-rc1', 'v8.0.4\nEVIL=true', '$(command)', 'v08.0.4']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                upstreams.version_tuple(value)
        entry = self.lock['cpa']
        self.replies[f'repos/{entry["repository"]}/releases/latest']['prerelease'] = True
        with self.assertRaisesRegex(ValueError, 'prerelease'):
            upstreams.next_lock(self.lock, self.get)

    def test_lock_matches_dockerfile(self):
        source = (ROOT / 'Dockerfile').read_text()
        self.assertEqual(upstreams.render_dockerfile(source, self.lock), source)
        with self.assertRaisesRegex(ValueError, 'exactly one'):
            upstreams.render_dockerfile(source + '\nARG CPA_VERSION=duplicate\n', self.lock)


if __name__ == '__main__':
    unittest.main()

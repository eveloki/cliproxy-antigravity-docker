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
        for entry in self.lock.values():
            if not isinstance(entry, dict):
                continue
            repo, tag = entry['repository'], entry['version']
            self.replies[f'repos/{repo}/releases/latest'] = {'tag_name': tag, 'draft': False, 'prerelease': False}
            self.replies[f'repos/{repo}/git/ref/tags/{tag}'] = {'object': {'type': 'commit', 'sha': entry['commit']}}

    def get(self, path):
        return self.replies[path]

    def test_unchanged_is_idempotent(self):
        self.assertEqual(upstreams.next_lock(self.lock, self.get), self.lock)

    def test_patch_update_and_annotated_tag(self):
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
        self.assertEqual(self.lock, before)

    def test_moved_tag_is_rejected(self):
        entry = self.lock['cpa']
        self.replies[f'repos/{entry["repository"]}/git/ref/tags/{entry["version"]}']['object']['sha'] = 'f' * 40
        with self.assertRaisesRegex(ValueError, 'tag moved'):
            upstreams.next_lock(self.lock, self.get)

    def test_major_upgrade_and_downgrade_are_rejected(self):
        entry = self.lock['cpa']
        major, minor, patch = upstreams.version_tuple(entry['version'])
        reply = self.replies[f'repos/{entry["repository"]}/releases/latest']
        for version, error in [(f'v{major + 1}.0.0', 'Major version'), (f'v{major - 1}.0.0', 'downgrade')]:
            with self.subTest(version=version):
                reply['tag_name'] = version
                with self.assertRaisesRegex(ValueError, error):
                    upstreams.next_lock(self.lock, self.get)

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

"""Synthetic old-volume state and upgrade assertions, executed only inside CI containers."""
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import urllib.request
import uuid
import yaml

HOME = Path('/home/cliproxy')
BASELINE = Path('/config/upgrade-baseline.json')


def fingerprint(path):
    stat = path.stat()
    data = path.read_bytes() if path.is_file() else None
    # CPA may reserialize native Codex JSON through its atomic credential writer.
    # Compare every field; opaque files still require byte-for-byte preservation.
    if data is not None and path.name == 'upgrade-codex.json':
        data = json.dumps(json.loads(data), sort_keys=True, separators=(',', ':')).encode()
    return {'sha256': hashlib.sha256(data).hexdigest() if data is not None else None,
            'mode': stat.st_mode & 0o777, 'uid': stat.st_uid, 'gid': stat.st_gid}


def config_identity_transition(before, after):
    """Allow only CPA's first nonzero canonical server UUID, preserving every setting."""
    before, after = copy.deepcopy(before), copy.deepcopy(after)
    old_server, new_server = before.get('server', {}), after.get('server', {})
    assert isinstance(old_server, dict) and isinstance(new_server, dict), 'Invalid server config'
    assert not old_server.get('server-id'), 'Existing server identity cannot change'
    value = new_server.get('server-id')
    assert isinstance(value, str), 'Missing generated server identity'
    parsed = uuid.UUID(value)
    assert parsed.int != 0 and str(parsed) == value, 'Invalid generated server UUID'
    old_server.pop('server-id', None)
    new_server.pop('server-id', None)
    if not old_server:
        before.pop('server', None)
    if not new_server:
        after.pop('server', None)
    assert before == after, 'Unexpected configuration parameter change'


def config_comments(text):
    return [line.lstrip() for line in text.splitlines() if line.lstrip().startswith('#')]


def verify_config(path, expected, phase, accepted_path):
    actual = fingerprint(path)
    original = {key: expected[key] for key in ('sha256', 'mode', 'uid', 'gid')}
    if accepted_path.exists():
        assert actual == json.loads(accepted_path.read_text()), 'Accepted config/identity changed after recreation or rollback'
        return
    if actual == original:
        return
    assert phase == 'new', 'Unexpected config change before upgrade'
    assert {k: actual[k] for k in ('mode', 'uid', 'gid')} == {k: original[k] for k in ('mode', 'uid', 'gid')}, 'Config permissions/ownership changed'
    text = path.read_text()
    config_identity_transition(expected['yaml'], yaml.safe_load(text))
    assert config_comments(text) == expected['comments'], 'Original config comments changed'
    # Pin the exact post-upgrade bytes and metadata for recreation AND rollback.
    accepted_path.write_text(json.dumps(actual))
    print('PASS: only first server.server-id was added; all original config values/comments and metadata preserved.')


def main():
    if sys.argv[1] == 'record':
        assert os.getuid() == 10001
        assert not (HOME / 'plugins').exists(), 'Fixture must be created by the old RC image'
        config = Path('/config/config.yaml')
        cfg = yaml.safe_load(config.read_text())
        assert cfg['plugins']['dir'] == '/opt/cliproxy/plugins'
        # Never real credentials: old opaque file state and a disabled CPA credential.
        fixtures = {
            '.gemini/upgrade-state.txt': 'synthetic CLI state\n',
            '.cli-proxy-api/upgrade-codex.json': json.dumps({'type': 'codex', 'disabled': True,
                'email': 'upgrade@example.invalid', 'access_token': 'synthetic-not-a-token'}),
            'workspace/existing.db': 'synthetic persistent database\n',
            '.local/bin/agy': '#!/bin/sh\nexit 97\n',
        }
        for relative, value in fixtures.items():
            path = HOME / relative
            path.write_text(value)
            path.chmod(0o700 if relative == '.local/bin/agy' else 0o600)
        paths = [config, HOME, Path('/config')] + [HOME / x for x in fixtures]
        snapshots = {str(p): fingerprint(p) for p in paths}
        snapshots[str(config)].update(yaml=cfg, comments=config_comments(config.read_text()))
        BASELINE.write_text(json.dumps(snapshots))
    else:
        assert os.getuid() == 10001 and os.environ['HOME'] == str(HOME)
        assert os.environ['AGY_HOME'] == str(HOME)
        assert os.getcwd() == str(HOME / 'workspace')
        for filename, expected in json.loads(BASELINE.read_text()).items():
            if filename == '/config/config.yaml':
                verify_config(Path(filename), expected, sys.argv[1], Path('/config/upgrade-config-accepted.json'))
            else:
                assert fingerprint(Path(filename)) == expected, filename + ' changed'
        if sys.argv[1] == 'new':
            directory = HOME / 'plugins'
            assert Path('/opt/cliproxy/plugins').is_symlink()
            assert directory.stat().st_uid == 10001
            bundled = Path('/opt/cliproxy/bundled-plugins/cliproxy-antigravity.so')
            assert (directory / bundled.name).read_bytes() == bundled.read_bytes()
            assert (directory / '.cliproxy-antigravity.so.bundled-sha256').is_file()
        config = yaml.safe_load(Path('/config/config.yaml').read_text())
        request = urllib.request.Request('http://127.0.0.1:8317/v1/models', headers={
            'Authorization': 'Bearer ' + config['access']['api-keys'][0]})
        expected_model = 'agy/' + os.environ['CLIPROXY_TEST_MODEL']
        for attempt in range(30):
            with urllib.request.urlopen(request, timeout=5) as response:
                models = json.load(response)['data']
            if any(model['id'] == expected_model for model in models):
                break
            time.sleep(1)
        else:
            raise AssertionError('Plugin model missing after upgrade/rollback')
        print('PASS: original config/key, synthetic credential/state/data, permissions and UID preserved; plugin model loaded.')


if __name__ == '__main__':
    main()

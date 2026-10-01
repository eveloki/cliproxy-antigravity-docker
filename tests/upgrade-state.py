"""Synthetic old-volume state and upgrade assertions, executed only inside CI containers."""
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import urllib.request
import yaml

HOME = Path('/home/cliproxy')
BASELINE = Path('/config/upgrade-baseline.json')


def fingerprint(path):
    stat = path.stat()
    return {'sha256': hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None,
            'mode': stat.st_mode & 0o777, 'uid': stat.st_uid, 'gid': stat.st_gid}


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
    BASELINE.write_text(json.dumps({str(p): fingerprint(p) for p in paths}))
else:
    assert os.getuid() == 10001 and os.environ['HOME'] == str(HOME)
    assert os.environ['AGY_HOME'] == str(HOME)
    assert os.getcwd() == str(HOME / 'workspace')
    for filename, expected in json.loads(BASELINE.read_text()).items():
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

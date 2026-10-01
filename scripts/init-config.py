#!/usr/bin/env python3
"""Initialize a private config once. Never rotate keys on restart."""
import fcntl
import os
from pathlib import Path
import secrets
import tempfile
import sys
from runtime_config import config_path


def initialize(directory=Path('/CLIProxyAPI'), template=Path('/opt/cliproxy/config.example.yaml'), filename='config.yaml'):
    target = directory / filename
    if target.is_file():
        return
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / '.init.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if target.exists():
            return
        content = template.read_text()
        if content.count('__GENERATED_CLIENT_KEY__') != 1:
            raise ValueError('Expected exactly one API-key placeholder')
        content = content.replace('__GENERATED_CLIENT_KEY__', 'sk-' + secrets.token_hex(32))
        if os.environ.get('HOME') == '/home/cliproxy':
            content = content.replace('/root/.cli-proxy-api', '/home/cliproxy/.cli-proxy-api')
            content = content.replace('/CLIProxyAPI/plugins', '/home/cliproxy/plugins')
            content = content.replace('/CLIProxyAPI/data/agy-workspace', '/home/cliproxy/workspace')
        fd, name = tempfile.mkstemp(prefix='.config-', dir=directory)
        try:
            with os.fdopen(fd, 'w') as output:
                output.write(content)
                output.flush()
                os.fsync(output.fileno())
            os.replace(name, target)
        finally:
            Path(name).unlink(missing_ok=True)
    print(f'Created {target} with a random client API key (not logged).')


if __name__ == '__main__':
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else config_path(use_state=False)
    initialize(path.parent, filename=path.name)

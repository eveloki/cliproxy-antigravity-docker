#!/usr/bin/env python3
"""Initialize a private config once. Never rotate keys on restart."""
import fcntl
import os
from pathlib import Path
import secrets
import tempfile


def initialize(directory=Path('/config'), template=Path('/opt/cliproxy/config.example.yaml')):
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / '.init.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        target = directory / 'config.yaml'
        if target.exists():
            return
        content = template.read_text()
        if content.count('__GENERATED_CLIENT_KEY__') != 1:
            raise ValueError('Expected exactly one API-key placeholder')
        content = content.replace('__GENERATED_CLIENT_KEY__', 'sk-' + secrets.token_hex(32))
        fd, name = tempfile.mkstemp(prefix='.config-', dir=directory)
        try:
            with os.fdopen(fd, 'w') as output:
                output.write(content)
                output.flush()
                os.fsync(output.fileno())
            os.replace(name, target)
        finally:
            Path(name).unlink(missing_ok=True)
    print('Created /config/config.yaml with a random client API key (not logged).')


if __name__ == '__main__':
    initialize()

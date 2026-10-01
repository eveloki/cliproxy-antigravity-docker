#!/usr/bin/env python3
"""Seed the bundled plugin into a writable configured directory, preserving user files."""
import fcntl
import hashlib
import os
from pathlib import Path
import sys
import tempfile
from runtime_config import load

BUNDLED = Path('/opt/cliproxy/bundled-plugins/cliproxy-antigravity.so')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def seed(source, directory):
    # Old named volumes mask image-created directories. Follow the compatibility
    # symlink before mkdir so its missing target is created inside the mounted HOME.
    directory = directory.resolve()
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / source.name
    marker = directory / ('.' + source.name + '.bundled-sha256')
    with (directory / '.bundled-plugin.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        expected = digest(source)
        if target.is_symlink():
            print('Preserving user-managed plugin symlink: ' + str(target), file=sys.stderr)
            return
        if target.exists():
            actual = digest(target)
            if actual == expected:
                return
            if not marker.is_file() or marker.read_text().strip() != actual:
                print('Preserving user-managed plugin: ' + str(target), file=sys.stderr)
                return
        fd, temp = tempfile.mkstemp(prefix='.bundled-', dir=directory)
        try:
            with os.fdopen(fd, 'wb') as output:
                output.write(source.read_bytes())
                output.flush()
                os.fsync(output.fileno())
            Path(temp).chmod(0o755)
            os.replace(temp, target)
            marker.write_text(expected + '\n')
        finally:
            Path(temp).unlink(missing_ok=True)


def prepare(path):
    cfg = load(path)
    plugins = cfg.get('plugins') or {}
    if not plugins.get('enabled', False):
        return
    instance = (plugins.get('configs') or {}).get('cliproxy-antigravity') or {}
    if not instance.get('enabled', False):
        return
    directory = Path(str(plugins.get('dir') or 'plugins').strip()).expanduser()
    seed(BUNDLED, directory)
    if instance.get('workdir'):
        Path(instance['workdir']).expanduser().resolve().mkdir(parents=True, exist_ok=True)


if __name__ == '__main__':
    prepare(Path(sys.argv[1]))

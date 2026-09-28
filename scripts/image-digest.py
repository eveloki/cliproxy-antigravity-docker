#!/usr/bin/env python3
"""Read a registry digest; only an exact missing manifest is treated as absent."""
import json
import re
import subprocess
import sys


def image_digest(reference, run=subprocess.run):
    result = run(
        ['docker', 'buildx', 'imagetools', 'inspect', reference, '--format', '{{json .Manifest}}'],
        capture_output=True, text=True, timeout=120,
    )
    if result.returncode:
        # Do not confuse denied access, network failures or invalid responses with
        # a free tag: that could allow overwriting an already published version.
        if result.stderr.strip() == f'ERROR: {reference}: not found':
            return ''
        raise RuntimeError(f'Cannot determine registry state: {result.stderr.strip()}')
    digest = json.loads(result.stdout).get('digest', '')
    if not re.fullmatch(r'sha256:[0-9a-f]{64}', digest):
        raise ValueError('Registry returned an invalid digest')
    return digest


if __name__ == '__main__':
    print(image_digest(sys.argv[1]))

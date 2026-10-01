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


def publication_needed(image, version, inspect=image_digest):
    # Read every tag even if one is missing: registry errors must fail closed.
    version_digest, stable_digest, latest_digest = (
        inspect(f'{image}:{tag}') for tag in (version, 'stable', 'latest')
    )
    return not (version_digest and stable_digest == version_digest == latest_digest)


if __name__ == '__main__':
    if sys.argv[1] == '--publication-needed':
        print(str(publication_needed(sys.argv[2], sys.argv[3])).lower())
    else:
        print(image_digest(sys.argv[1]))

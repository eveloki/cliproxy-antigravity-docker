#!/usr/bin/env python3
"""Track latest stable releases; snapshot exact inputs for reproducible RC builds."""
import argparse
import copy
import json
import os
from pathlib import Path
import re
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
REPOSITORIES = {'cpa': 'router-for-me/CLIProxyAPI', 'plugin': 'adeebahmad01/cliproxy-antigravity'}


def version_tuple(value):
    match = re.fullmatch(r'v?(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)', value)
    if not match:
        raise ValueError(f'Expected stable x.y.z version, got {value!r}')
    return tuple(map(int, match.groups()))


def api(path):
    headers = {'Accept': 'application/vnd.github+json', 'User-Agent': 'cliproxy-docker-updater'}
    token = os.environ.get('GH_TOKEN')
    if token:
        headers['Authorization'] = 'Bearer ' + token
    request = urllib.request.Request('https://api.github.com/' + path, headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def release_commit(repository, tag, get=api):
    ref = get(f'repos/{repository}/git/ref/tags/{urllib.parse.quote(tag, safe="")}')['object']
    for _ in range(8):
        if not re.fullmatch(r'[0-9a-f]{40}', ref.get('sha', '')):
            raise ValueError('Invalid upstream SHA')
        if ref.get('type') == 'commit':
            return ref['sha']
        if ref.get('type') != 'tag':
            raise ValueError('Release tag does not resolve to a commit')
        ref = get(f'repos/{repository}/git/tags/{ref["sha"]}')['object']
    raise ValueError('Excessive annotated tag nesting')


def next_lock(current, get=api):
    proposed = copy.deepcopy(current)
    for key, repository in REPOSITORIES.items():
        old = current[key]
        if old['repository'] != repository:
            raise ValueError('Unexpected upstream repository')
        release = get(f'repos/{repository}/releases/latest')
        if release.get('draft') or release.get('prerelease'):
            raise ValueError('Refusing draft or prerelease')
        version = release['tag_name']
        old_version, new_version = version_tuple(old['version']), version_tuple(version)
        if new_version < old_version:
            raise ValueError(f'Refusing downgrade: {old["version"]} -> {version}')
        commit = release_commit(repository, version, get)
        if new_version == old_version and commit != old['commit']:
            raise ValueError(f'Upstream tag moved without a version change: {version}')
        proposed[key] = {'repository': repository, 'version': version, 'commit': commit}
    if any(proposed[key] != current[key] for key in REPOSITORIES):
        proposed['packaging_revision'] = 1
    return proposed


def image_tag(lock):
    versions = ['.'.join(map(str, version_tuple(lock[key]['version']))) for key in REPOSITORIES]
    revision = lock.get('packaging_revision', 1)
    if type(revision) is not int or revision < 1:
        raise ValueError('packaging_revision must be a positive integer')
    agy = validate_agy(lock)
    return 'v' + '-'.join(versions) + f'-agy{agy["version"]}-rc.{revision}'


def validate_agy(lock):
    agy = lock['agy']
    if agy['repository'] != 'google-antigravity/antigravity-cli':
        raise ValueError('Unexpected CLI repository')
    version_tuple(agy['version'])
    if agy['version'].startswith('v') or agy['asset'] != 'agy_cli_linux_x64.tar.gz':
        raise ValueError('Unexpected CLI version or amd64 asset')
    if not re.fullmatch(r'[0-9a-f]{64}', agy['sha256']):
        raise ValueError('Invalid CLI SHA256')
    return agy


def render_dockerfile(content, lock):
    agy = validate_agy(lock)
    for field in ('version', 'sha256'):
        arg = f'AGY_{field.upper()}'
        content, count = re.subn(rf'^ARG {arg}=.*$', f'ARG {arg}={agy[field]}', content, flags=re.M)
        if count != 1:
            raise ValueError(f'Expected exactly one {arg} build argument')
    for key in REPOSITORIES:
        version_tuple(lock[key]['version'])
        if not re.fullmatch(r'[0-9a-f]{40}', lock[key]['commit']):
            raise ValueError('Invalid lock SHA')
        for field in ('commit', 'version'):
            arg = f'{key.upper()}_{field.upper()}'
            content, count = re.subn(rf'^ARG {arg}=.*$', f'ARG {arg}={lock[key][field]}', content, flags=re.M)
            if count != 1:
                raise ValueError(f'Expected exactly one {arg} build argument')
    return content


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--update', action='store_true', help='Query upstream and write candidate lock/Dockerfile')
    args = parser.parse_args()
    lock_path, docker_path = ROOT / 'upstream-versions.json', ROOT / 'Dockerfile'
    current = json.loads(lock_path.read_text())
    if current.get('schema') != 1:
        raise ValueError('Unsupported lock schema')
    image_tag(current)
    dockerfile = docker_path.read_text()
    if render_dockerfile(dockerfile, current) != dockerfile:
        raise ValueError('Dockerfile pins disagree with upstream-versions.json')
    proposed = next_lock(current) if args.update else current
    updated_dockerfile = render_dockerfile(dockerfile, proposed)
    changed = proposed != current
    if changed:
        docker_path.write_text(updated_dockerfile)
        lock_path.write_text(json.dumps(proposed, indent=2) + '\n')
    suffix = f'cpa-{proposed["cpa"]["version"].lstrip("v")}-plugin-{proposed["plugin"]["version"].lstrip("v")}-agy-{proposed["agy"]["version"]}'
    outputs = {'changed': str(changed).lower(), 'version_suffix': suffix, 'image_tag': image_tag(proposed)}
    if os.environ.get('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'], 'a') as output:
            for key, value in outputs.items():
                output.write(f'{key}={value}\n')
    print(json.dumps(outputs))


if __name__ == '__main__':
    main()

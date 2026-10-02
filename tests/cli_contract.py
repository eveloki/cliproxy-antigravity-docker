"""Strict CLI contract checks, keeping Docker's stdout/stderr independent."""
import difflib
import subprocess
import sys


def probe(label, command):
    try:
        result = subprocess.run(command, capture_output=True, timeout=60)
    except subprocess.TimeoutExpired as exc:
        raise AssertionError(f'{label}: timed out after 60s; stdout={exc.stdout!r}; stderr={exc.stderr!r}') from exc
    if result.returncode:
        raise AssertionError(f'{label}: exit={result.returncode}; stdout={result.stdout!r}; stderr={result.stderr!r}')
    return result


def compare(label, native, wrapped):
    for stream in ('stdout', 'stderr'):
        before, after = getattr(native, stream), getattr(wrapped, stream)
        if before != after:
            diff = ''.join(difflib.unified_diff(
                before.decode(errors='backslashreplace').splitlines(keepends=True),
                after.decode(errors='backslashreplace').splitlines(keepends=True),
                fromfile=f'native/{stream}', tofile=f'wrapped/{stream}'))
            raise AssertionError(f'{label}: {stream} differs\n{diff}\nnative={before!r}\nwrapped={after!r}')


def main(image, expected):
    version = probe('agy --version', ['docker', 'run', '--rm', '--network', 'none', image, 'agy', '--version'])
    if version.stdout.decode().strip() != expected:
        raise AssertionError(f'agy version: expected={expected!r}; stdout={version.stdout!r}; stderr={version.stderr!r}')
    print(f'PASS: wrapped agy version is {expected}.', flush=True)
    for args in (['-help'], ['discover', '--help']):
        label = ' '.join(args)
        common = ['docker', 'run', '--rm', '--network', 'none', '--read-only', '--tmpfs', '/tmp']
        native = probe(f'native {label}', common + ['--entrypoint', '/CLIProxyAPI/CLIProxyAPI', image] + args)
        wrapped = probe(f'wrapped {label}', common + [image, './CLIProxyAPI'] + args)
        compare(label, native, wrapped)
        print(f'PASS: {label}: exit=0; stdout and stderr exactly match native CPA on a read-only rootfs.', flush=True)


if __name__ == '__main__':
    main(*sys.argv[1:])

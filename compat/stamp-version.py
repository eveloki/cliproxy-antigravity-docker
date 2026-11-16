"""Verify pinned upstream version before giving the custom build its identity."""
from pathlib import Path
import re
import sys


def stamp(path, expected):
    expected = expected.removeprefix('v')
    if not re.fullmatch(r'\d+\.\d+\.\d+', expected):
        raise ValueError('Expected a stable plugin version')
    path = Path(path)
    source = path.read_text()
    pattern = r'(\bpluginVersion\s*=\s*)"([^"\n]+)"'
    found = list(re.finditer(pattern, source))
    if len(found) != 1 or found[0][2] != expected:
        raise ValueError('Pinned plugin version does not match source; review before building')
    source = re.sub(pattern, lambda m: m[1] + '"' + expected + '+dist1"', source)
    path.write_text(source)


if __name__ == '__main__':
    stamp(*sys.argv[1:])

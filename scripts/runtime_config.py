"""Shared runtime paths and legacy/v8 config access for distribution helpers."""
import json
import os
from pathlib import Path
import sys
import yaml

STATE = Path(os.environ.get('CPA_RUNTIME_STATE', '/tmp/cliproxy-runtime.json'))

# Match CPA's argvFlagConsumesValue: these native flags do not consume the next
# argument. Unknown flags are left for CPA to validate (plugins may add flags).
BOOL_FLAGS = frozenset('codex-login codex-device-login claude-login no-browser '
    'antigravity-login kimi-login kimi-ai-login xai-login devin-login meta-login '
    'discover discover-json home-disable-cluster-discovery tui standalone local-model h help'.split())


def explicit_config(args):
    selected = None
    index = 0
    while index < len(args):
        arg = args[index]
        if arg in ('--', '-') or not arg.startswith('-'):
            break
        name, equal, value = arg.lstrip('-').partition('=')
        if not equal and name not in BOOL_FLAGS:
            index += 1
            if index == len(args):
                raise ValueError('Missing value for -' + name)
            value = args[index]
        if name == 'config':
            selected = Path(value).absolute() if value else Path.cwd() / 'config.yaml'
        index += 1
    return selected


def config_path(args=(), use_state=True):
    selected = explicit_config(args)
    if selected is not None:
        return selected
    if use_state and STATE.is_file():
        return Path(json.loads(STATE.read_text())['config'])
    if os.environ.get('CPA_CONFIG'):
        return Path(os.environ['CPA_CONFIG']).absolute()
    standard = Path('/CLIProxyAPI/config.yaml')
    legacy = Path('/config/config.yaml')
    return legacy if not standard.exists() and legacy.is_file() else standard


def load(path=None):
    data = yaml.safe_load((path or config_path()).read_text())
    if not isinstance(data, dict):
        raise ValueError('Config must be a mapping')
    return data


def field(data, section, key, default=None):
    nested = data.get(section)
    if isinstance(nested, dict) and key in nested:
        return nested[key]
    return data.get(key, default)


def client_key(data):
    keys = field(data, 'access', 'api-keys', [])
    return keys[0] if isinstance(keys, list) and keys else ''


def endpoint(data):
    host = field(data, 'server', 'host', '')
    if host in ('', '0.0.0.0'):
        host = '127.0.0.1'
    elif host == '::':
        host = '[::1]'
    elif ':' in host and not host.startswith('['):
        host = '[' + host + ']'
    tls = field(data, 'server', 'tls', {}) or {}
    scheme = 'https' if tls.get('enable', False) else 'http'
    return f'{scheme}://{host}:{field(data, "server", "port", 8317)}'


if __name__ == '__main__':
    action = sys.argv[1]
    if action == 'path':
        print(config_path(sys.argv[2:], use_state=False))
    elif action == 'record':
        STATE.write_text(json.dumps({'config': sys.argv[2]}))
        STATE.chmod(0o600)
    elif action == 'key':
        print(client_key(load()))
    else:
        raise SystemExit('Unknown runtime-config action')

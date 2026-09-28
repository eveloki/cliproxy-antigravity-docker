#!/usr/bin/env python3
"""Local authenticated /v1/models liveness; NOT an upstream auth check."""
import json
import urllib.request
from pathlib import Path
import yaml

try:
    config = yaml.safe_load(Path('/config/config.yaml').read_text())
    key = config['access']['api-keys'][0]
    request = urllib.request.Request('http://127.0.0.1:8317/v1/models',
                                     headers={'Authorization': 'Bearer ' + key})
    with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(request, timeout=3) as response:
        payload = json.load(response)
    assert isinstance(payload.get('data'), list)
except Exception:
    raise SystemExit(1)

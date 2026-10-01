#!/usr/bin/env python3
"""Local authenticated /v1/models liveness; NOT an upstream auth check."""
import json
import urllib.request
from pathlib import Path
import ssl
from runtime_config import load, client_key, endpoint

try:
    config = load()
    key = client_key(config)
    request = urllib.request.Request(endpoint(config) + '/v1/models',
                                     headers={'Authorization': 'Bearer ' + key})
    with urllib.request.build_opener(urllib.request.ProxyHandler({}),
        urllib.request.HTTPSHandler(context=ssl._create_unverified_context())).open(request, timeout=3) as response:
        payload = json.load(response)
    assert isinstance(payload.get('data'), list)
except Exception:
    raise SystemExit(1)

"""Test real CPA/plugin error propagation using synthetic early-finished CLI output."""
import json
import os
from pathlib import Path
import urllib.error
import urllib.request

url = os.environ.get('CPA_TEST_URL', 'http://127.0.0.1:8317') + '/v1/chat/completions'
key = os.environ.get('CPA_TEST_KEY')
if not key:
    import yaml
    key = yaml.safe_load(Path('/config/config.yaml').read_text())['access']['api-keys'][0]
headers = {'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'}
flag = Path(os.environ.get('AGY_HOME', os.environ['HOME'])) / 'mock-finished-reason'
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
try:
    for reason in ('print_timeout', 'interrupted', 'error', 'future_reason'):
        flag.write_text(reason)
        for stream in (False, True):
            body = {'model': 'agy/' + os.environ['CLIPROXY_TEST_MODEL'],
                    'messages': [{'role': 'user', 'content': 'test early finish'}], 'stream': stream}
            request = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers)
            try:
                with opener.open(request, timeout=15) as response:
                    content = response.read().decode()
            except urllib.error.HTTPError as error:
                assert error.code == (504 if reason == 'print_timeout' else 502), (reason, error.code)
                content = error.read().decode()
                assert 'error' in json.loads(content), content
            else:
                assert stream, 'Non-streaming partial completion was accepted'
                events = [json.loads(line[5:].strip()) for line in content.splitlines()
                          if line.startswith('data:') and line[5:].strip() != '[DONE]']
                assert any(event.get('error') for event in events), content
                assert not any(choice.get('finish_reason') for event in events
                               for choice in event.get('choices', [])), content
    print('PASS: JSON and SSE never report success for timeout/interruption/error/unknown early finishes.')
finally:
    flag.unlink(missing_ok=True)

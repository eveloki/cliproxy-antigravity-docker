#!/usr/bin/env bash
set -euo pipefail
echo 'Distribution: NOT READY — PENDING TESTS'
cat /opt/cliproxy/upstream-versions.txt
agy --version
echo 'Checking agy model discovery (timeout 45 seconds)...'
timeout --kill-after=5s 45s agy models
echo 'Model discovery completed. This is NOT proof of successful model inference.'
echo 'Next: agy -p "Reply only with OK" and the documented recreation/tool tests.'

#!/usr/bin/env bash
set -euo pipefail
python3 - <<'PY'
import json, urllib.request
url = 'https://hub.docker.com/v2/repositories/stereolabs/zed/tags?page_size=100'
while url:
    with urllib.request.urlopen(url, timeout=20) as r:
        data = json.load(r)
    for item in data.get('results', []):
        name = item.get('name')
        pushed = item.get('tag_last_pushed', '')[:10]
        arch = ','.join(sorted({img.get('architecture','?') for img in item.get('images', [])}))
        print(f'{name}\t{pushed}\t{arch}')
    url = data.get('next')
PY

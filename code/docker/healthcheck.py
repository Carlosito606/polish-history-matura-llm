#!/usr/bin/env python3
"""Container healthcheck: exit 0 if any of the given URLs answers 2xx (stdlib only).

Usage: healthcheck.py [URL ...]   default: harness /health, then /v1/models
"""
import os
import sys
import urllib.request

port = os.environ.get("HARNESS_PORT", "18000")
urls = sys.argv[1:] or [f"http://127.0.0.1:{port}/health", f"http://127.0.0.1:{port}/v1/models"]
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))  # never use a proxy
for u in urls:
    try:
        with opener.open(u, timeout=4) as r:
            if 200 <= r.status < 300:
                sys.exit(0)
    except Exception:  # noqa: BLE001
        pass
sys.exit(1)

"""Small stdlib JSON fetch helper for source adapters."""

from __future__ import annotations

import json
import urllib.request
from typing import Dict, Optional


def fetch_json_url(url: str, headers: Optional[Dict[str, str]] = None) -> Dict:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "opc-dashboard-source-adapter/0.1",
            "Accept": "application/json",
            **(headers or {}),
        },
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))

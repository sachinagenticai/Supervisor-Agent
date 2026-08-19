from __future__ import annotations

import os
from urllib.request import urlopen

port = os.getenv("PORT", "8501")
with urlopen(f"http://127.0.0.1:{port}/_stcore/health", timeout=5) as response:
    if response.status != 200:
        raise SystemExit(1)

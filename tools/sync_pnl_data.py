#!/usr/bin/env python3
"""Read live-dashboard/data/pnl_history.json → embed into portal/index.html

Usage: python3 tools/sync_pnl_data.py
"""

import json
import re
import sys
from datetime import datetime
from pathlib import Path

LIVE_DASHBOARD = Path.home() / "Documents/YM_Capital/live-dashboard"
PORTAL = Path.home() / "Documents/YM_Capital/portal"


def main():
    src = LIVE_DASHBOARD / "data/pnl_history.json"
    target = PORTAL / "index.html"

    if not src.exists():
        print(f"ERROR: {src} not found")
        sys.exit(1)

    with open(src) as f:
        pnl_data = json.load(f)

    js_blob = f"<script>\nconst PNL_DATA = {json.dumps(pnl_data, ensure_ascii=False)};\n</script>"

    with open(target) as f:
        html = f.read()

    pattern = r"(<!-- PNL_DATA_START -->)(.*?)(<!-- PNL_DATA_END -->)"
    replacement = f"\\1\n{js_blob}\n  \\3"

    new_html = re.sub(pattern, replacement, html, flags=re.DOTALL)

    if new_html == html:
        print("ERROR: PNL_DATA markers not found in index.html")
        sys.exit(1)

    # Backfill benchmark data if all zeros
    # ...

    with open(target, "w") as f:
        f.write(new_html)

    n = len(pnl_data.get("daily", []))
    print(f"[done] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} — synced {n} daily entries → portal/index.html")


if __name__ == "__main__":
    main()

"""Collect VLESS configs, keep only the ones that actually work, write a sub.

Pipeline: read sources -> fetch (decode base64 if needed) -> parse vless only ->
clean (drop localhost/private/dupes) -> test through xray -> write base64
subscription + README stats.
"""
import base64
import os
import sys
import urllib.request
from datetime import datetime, timezone

import vless
import tester

SOURCES_FILE = "sources.txt"
OUT_SUB = "sub.txt"          # base64 subscription, import directly into clients
OUT_PLAIN = "vless.txt"      # human-readable, one config per line
README = "README.md"
FETCH_TIMEOUT = 15
# Cap how many nodes we test through xray (0 = no cap). Keeps Actions runtime
# bounded; dropped nodes are logged, never silently truncated.
MAX_TEST = int(os.environ.get("MAX_TEST", "0"))


def read_sources():
    with open(SOURCES_FILE, encoding="utf-8") as f:
        return [ln.strip() for ln in f if ln.strip() and not ln.startswith("#")]


def fetch(url):
    """Return raw text lines from a source; decodes base64 blobs transparently."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "vless-collector"})
        raw = urllib.request.urlopen(req, timeout=FETCH_TIMEOUT).read().decode("utf-8", "ignore")
    except Exception as e:
        print(f"  ! {url}: {e}", file=sys.stderr)
        return []
    if "vless://" not in raw:
        # Probably base64. Pad and decode.
        try:
            decoded = base64.b64decode(raw + "=" * (-len(raw) % 4)).decode("utf-8", "ignore")
            if "vless://" in decoded:
                raw = decoded
        except Exception:
            pass
    return raw.splitlines()


def collect():
    """Fetch + parse + clean. Returns deduped list of clean vless nodes."""
    seen, nodes = set(), []
    for url in read_sources():
        count = 0
        for line in fetch(url):
            line = line.strip()
            if "vless://" not in line:
                continue
            node = vless.parse(line[line.index("vless://"):])
            if not node or not vless.is_clean(node):
                continue
            key = vless.dedupe_key(node)
            if key in seen:
                continue
            seen.add(key)
            nodes.append(node)
            count += 1
        print(f"  + {url.split('/')[-1] or url}: {count} new")
    return nodes


def write_outputs(live):
    """live = list of (node, latency_ms), fastest first."""
    uris = [node["uri"] for node, _ in live]
    blob = "\n".join(uris)
    with open(OUT_PLAIN, "w", encoding="utf-8") as f:
        f.write(blob + "\n")
    with open(OUT_SUB, "w", encoding="utf-8") as f:
        f.write(base64.b64encode(blob.encode("utf-8")).decode("ascii"))
    _write_readme(len(live), live[0][1] if live else None)


def _write_readme(n, fastest_ms):
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    slug = os.environ.get("REPO_SLUG", "mehrtat/vless-collector")
    raw_base = f"https://raw.githubusercontent.com/{slug}/main"
    body = f"""# VLESS Collector

Auto-collected **VLESS** configs, deduplicated, cleaned, and **tested through xray**
so only nodes that actually pass traffic are published. Updates every hour via
GitHub Actions.

**Last update:** {now}
**Working nodes:** {n}{f"  |  **Fastest:** {fastest_ms} ms" if fastest_ms else ""}

## Subscription

Import this URL into v2rayNG / v2rayN / nekoray / sing-box (base64 subscription):

```
{raw_base}/sub.txt
```

Or the plain list (one config per line): `{raw_base}/vless.txt`

## How it works

1. Fetch VLESS configs from the sources in `sources.txt` (latest content each run).
2. Keep only `vless://`, drop duplicates and bad hosts (localhost, 127.0.0.1, private IPs).
3. Start xray per node and request `generate_204` through it — keep only live nodes.
4. Sort by latency (fastest first) and publish `sub.txt` + `vless.txt`.

> Configs are sourced from public repositories. Use at your own risk.
"""
    with open(README, "w", encoding="utf-8") as f:
        f.write(body)


def main():
    print("Collecting…")
    nodes = collect()
    print(f"Clean unique vless nodes: {len(nodes)}")
    if not nodes:
        print("Nothing to test; leaving previous output untouched.", file=sys.stderr)
        return 1
    if MAX_TEST and len(nodes) > MAX_TEST:
        print(f"Capping test set: {len(nodes)} -> {MAX_TEST} (MAX_TEST); "
              f"{len(nodes) - MAX_TEST} nodes skipped this run.", file=sys.stderr)
        nodes = nodes[:MAX_TEST]
    print(f"Testing through xray (concurrency={tester.CONCURRENCY})…")
    live = tester.test_all(nodes)
    print(f"Working nodes: {len(live)} / {len(nodes)}")
    if not live:
        # Don't clobber a good published list with an empty one.
        print("No working nodes this run; keeping previous output.", file=sys.stderr)
        return 1
    write_outputs(live)
    print(f"Wrote {OUT_SUB}, {OUT_PLAIN}, {README}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

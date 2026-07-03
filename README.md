# VLESS Collector

Auto-collected **VLESS** configs, deduplicated, cleaned, and **tested through xray**
so only nodes that actually pass traffic are published. Updates every hour via
GitHub Actions.

**Last update:** 2026-07-03 21:01 UTC
**Working nodes:** 496  |  **Fastest:** 86 ms

## Subscription

Import this URL into v2rayNG / v2rayN / nekoray / sing-box (base64 subscription):

```
https://raw.githubusercontent.com/mehrtat/vless-collector/main/sub.txt
```

Or the plain list (one config per line): `https://raw.githubusercontent.com/mehrtat/vless-collector/main/vless.txt`

## How it works

1. Fetch VLESS configs from the sources in `sources.txt` (latest content each run).
2. Keep only `vless://`, drop duplicates and bad hosts (localhost, 127.0.0.1, private IPs).
3. Start xray per node and request `generate_204` through it — keep only live nodes.
4. Sort by latency (fastest first) and publish `sub.txt` + `vless.txt`.

> Configs are sourced from public repositories. Use at your own risk.

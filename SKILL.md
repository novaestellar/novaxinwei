---
name: novaxinwei
version: 1.1.0
description: "NovaXinWei (新信微) — web recon with WAF bypass, parallel fetch, dork databases, and 15 social platform channels"
triggers:
  - novaxinwei
  - web recon
  - fetch url
  - waf bypass
  - dorks
  - shodan dork
  - github dork
  - parallel fetch
  - xiaohongshu
  - bilibili
  - v2ex
  - social media fetch
  - threads
  - nodseek
  - nodloc
  - pojie
capabilities:
  - WAF-bypass fetch chain (curl_cffi TLS impersonation + Playwright fallback)
  - 15 Phase 0 API routes (Reddit, YouTube, V2EX, Cnblogs, CSDN, Gitee, Codeberg, X/Twitter, Threads, Xiaohongshu, Bilibili, NodeSeek, NodeLoc, PoJie, Web)
  - 15 social platform channels
  - Shodan + GitHub dork databases
  - Parallel fetch (ThreadPoolExecutor)
dependencies:
  - curl_cffi>=0.15.0
  - httpx>=0.27.0
  - feedparser>=6.0
  - loguru>=0.7
  - rich>=13.0
  - yt-dlp>=2024.1
  - pyyaml>=6.0
---

# NovaXinWei (新信微)

Web recon engine with WAF bypass, parallel fetch, and dork databases.

## Quick Start

```bash
# Check channel availability
python -m novaxinwei check

# Fetch a URL through WAF-bypass chain
python -m novaxinwei fetch https://example.com

# Parallel fetch multiple URLs
python -m novaxinwei fetch-parallel url1 url2 url3 --workers 5

# Shodan dork lookup
python -m novaxinwei dorks shodan apache

# GitHub dork search
python -m novaxinwei dorks github password
```

## Capabilities

### 1. WAF-Bypass Fetch Chain
- Phase 0: Official API routes (15 platforms)
- Phase 1: URL transforms (mobile, JSON, RSS)
- Phase 2: TLS impersonation (curl_cffi, 3x retry)
- Phase 3: Playwright headless fallback

### 2. Social Platform Channels (15)
| Platform | Backend | Tier |
|----------|---------|------|
| Twitter/X | curl | 0 |
| YouTube | yt-dlp/curl | 0 |
| Reddit | curl | 0 |
| Facebook | curl | 0 |
| Instagram | curl | 0 |
| Bilibili | curl | 0 |
| Xiaohongshu | curl | 1 |
| LinkedIn | curl | 1 |
| V2EX | curl | 0 |
| Threads | oembed | 0 |
| NodeSeek | curl | 0 |
| NodeLoc | curl | 0 |
| PoJie | curl | 0 |
| RSS | curl | 0 |
| Web (catch-all) | curl | 0 |

### 3. Dork Databases
- **Shodan:** 126 dork patterns (7 categories)
- **GitHub:** 234 dork patterns (10 categories)

### 4. Parallel Fetch
```python
from novaxinwei.channels import fetch_parallel
results = fetch_parallel(["url1", "url2", "url3"], max_workers=5)
```

## Usage with Hermes

When user asks to:
- "Fetch URL" → use `python -m novaxinwei fetch <url>`
- "Recon target" → use fetch chain + dorks
- "Check social media" → use channel check
- "Parallel fetch" → use `fetch-parallel`

## Dependencies
- `curl_cffi` — TLS impersonation (required)
- `httpx` — HTTP client (required)
- `feedparser` — RSS/Atom parsing (required)
- `rich` — CLI output (required)
- `yt-dlp` — YouTube extraction (optional)
- `pyyaml` — Dork database parsing (required)

## No-Site-Name Rule
The engine never stores or logs site-specific data. All site specifics go through
runtime hints or observations, never to code. See `engine/bias_check.py`.

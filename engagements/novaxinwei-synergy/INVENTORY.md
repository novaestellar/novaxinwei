# NovaXinWei PHASE 0 INVENTORY

Generated: 2026-09-20 | Version: 1.1.0 | Total .py files: 44 | Total lines: ~6,400+

---

## 1. ALL .py FILES

### Root Package

| Path | Lines | Imports | Exports | Purpose |
|------|-------|---------|---------|---------|
| `__init__.py` | 11 | — | `__version__` | Package init, version declaration (1.1.0) |
| `__main__.py` | 34 | `sys`, `os`, `importlib` | `main` | CLI entrypoint for `python -m novaxinwei`. Imports `cli.main` |
| `cli.py` | 174 | `argparse`, `json`, `sys` | `main`, `build_parser` | Unified CLI: `fetch`, `fetch-parallel`, `dorks`, `check` subcommands |

### engine/ Directory (4,802 lines total)

| Path | Lines | Imports | Exports | Purpose |
|------|-------|---------|---------|---------|
| `engine/__init__.py` | 37 | `.validators`, `.waf_detector`, `.url_transforms`, `.fetch_chain`, `.content_safety` | `Verdict`, `ValidationResult`, `validate`, `CHALLENGE_MARKERS`, `detect`, `TRANSFORMS`, `apply_transform`, `fetch`, `FetchResult`, `Attempt`, `BEGIN/END_UNTRUSTED_WEB_CONTENT`, `ContentSafetyReport`, `analyze_untrusted_content`, `wrap_untrusted_content` | Engine public API surface |
| `engine/__main__.py` | 148 | `argparse`, `json`, `sys`, `.`, `.url_masking` | `main`, `build_parser` | Engine CLI: `python3 -m engine URL [opts]` |
| `engine/fetch_chain.py` | 1276 | `os`, `random`, `time`, `re`, `io`, `json`, `dataclasses`, `.content_safety`, `.validators`, `.waf_detector`, `.url_transforms`, `.transport`, `.executor`, `.learning`, `.observations_log`, `pypdf`(opt), `markdownify`(opt), `resiliparse`(opt), `pdfplumber`(opt) | `fetch`, `FetchResult`, `Attempt`, `fetch_many` | **Core**: WAF-bypass fetch chain with diversity-ordered TLS grid, content rescue extraction (PDF/JSON-LD/innerText/markdown), self-learning (U5), R6 failure gate, R7 API-first hint |
| `engine/phase0.py` | 700 | `importlib`, `json`, `re`, `shutil`, `subprocess`, `sys`, `curl_cffi`(lazy), `playwright.sync_api` | `route` | Official public-API router for 15 platforms. SANCTIONED exception to No-Site-Name Rule |
| `engine/waf_detector.py` | 214 | `fnmatch`, `os`, `re`, `yaml`(opt) | `detect`, `load_profile`, `_load_profiles`, `last_load_error`, `DetectionHit` | WAF-product detection from live response. Returns ranked (profile_id, confidence) pairs |
| `engine/validators.py` | 349 | `json`, `re`, `enum`, `dataclasses`, `bs4`(opt) | `Verdict`, `ValidationResult`, `validate`, `CHALLENGE_MARKERS`, `TERMINAL_NONSUCCESS` | 6-layer response classifier: status → hard markers → size fingerprint → JSON awareness → success_selectors → soft heuristics |
| `engine/transport.py` | 310 | `os`, `threading`, `time`, `dataclasses`, `functools`, `urllib.parse`, `curl_cffi`(lazy) | `SessionPool`, `POOL`, `pool_enabled`, `filter_available`, `available_impersonates` | Per-host curl_cffi session pool with root warmup, browser→cookie bridge, SSRF guard, transient retry |
| `engine/content_safety.py` | 155 | `json`, `re`, `hashlib`, `dataclasses`, `.url_masking` | `BEGIN/END_UNTRUSTED_WEB_CONTENT`, `CONTENT_TRUST_UNTRUSTED_PUBLIC_WEB`, `ContentSafetyReport`, `analyze_untrusted_content`, `wrap_untrusted_content` | Prompt-injection detection and untrusted content boundary wrapping |
| `engine/executor.py` | 434 | `importlib`, `json`, `os`, `shutil`, `subprocess`, `sys`, `tempfile`, `time`, `.validators`, `.waf_detector`, `.fetch_chain` | `run_playwright_fallback` | Capability-matched browser fallback: nodriver, patchright, Playwright Node.js templates, cookie bridge |
| `engine/learning.py` | 179 | `json`, `os`, `datetime`, `urllib.parse` | `enabled`, `default_path`, `is_real_failure`, `key_for`, `load`, `save`, `lookup`, `record_success`, `record_failure` | U5 self-learning: per-host route memory (TTL 30d, cap 500, 2-strike eviction) |
| `engine/observations_log.py` | 62 | `json`, `os`, `time`, `pathlib`, `urllib.parse`, `.url_masking` | `log_fetch` | Append-only JSONL operational observations to `observations/fetch-YYYY-MM-DD.jsonl` |
| `engine/bias_check.py` | 183 | `argparse`, `os`, `re`, `sys`, `pathlib` | `main` | No-Site-Name Rule CI checker. Scans engine/ for hardcoded site names |
| `engine/safety.py` | 91 | `ipaddress`, `os`, `socket`, `urllib.parse` | `classify_url`, `location_of`, `is_redirect`, `resolve_redirect`, `allow_private_default`, `DEFAULT_MAX_REDIRECTS` | SSRF/redirect safety guard: blocks private/loopback/link-local/metadata IPs |
| `engine/url_transforms.py` | 120 | `urllib.parse` | `TRANSFORMS`, `apply_transform`, `iter_transformed` | 5 domain-agnostic URL transforms: original, mobile_subdomain, am_prefix, m_prefix_subdomain, drop_www |
| `engine/url_masking.py` | 70 | `re`, `urllib.parse` | `mask_url` | Redacts credential-shaped query params and userinfo from URLs before logging |
| `engine/x_search.py` | 289 | `importlib`, `json`, `os`, `re`, `concurrent.futures`, `html`, `urllib.parse`, `.phase0`, `.x_search_types`, `.x_search_io` | `search_x`, `XSearchError`, `main` | X/Twitter keyword discovery: Brave, Yahoo, xAI search → Phase 0 validation |
| `engine/x_search_io.py` | 46 | `os`, `shutil`, `subprocess`, `curl_cffi` | `resolve_xai_credential`, `http_get`, `http_post_json` | HTTP boundaries + xAI credential resolution for X search |
| `engine/x_search_types.py` | 42 | `dataclasses` | `XPost`, `XSearchResult` | Typed result contracts for X keyword discovery |

### engine/templates/ (Python browser templates)

| Path | Lines | Purpose |
|------|-------|---------|
| `engine/templates/nodriver_fetch.py` | 48 | nodriver (raw CDP) headless fetch template |
| `engine/templates/patchright_fetch.py` | 49 | patchright (Playwright fork) headless fetch template |

### channels/ Directory (665 lines total)

| Path | Lines | Imports | Exports | Purpose |
|------|-------|---------|---------|---------|
| `channels/__init__.py` | 94 | `.base`, all 15 channel modules, `concurrent.futures` | `ALL_CHANNELS`, `get_channel`, `get_all_channels`, `fetch_parallel` | Channel registry, parallel fetch via ThreadPoolExecutor |
| `channels/base.py` | 70 | `abc`, `typing` | `Channel` (ABC) | Base class: `can_handle()`, `check()`, `ordered_backends()` |
| `channels/utils.py` | 168 | `ipaddress`, `os`, `re`, `shutil`, `socket`, `subprocess`, `pathlib`, `urllib.parse` | `host_matches`, `domain_matches`, `normalize_public_http_url`, `probe_command`, `scrub_url_credentials`, `home_dir`, `config_dir` | URL matching, SSRF-safe URL normalization, process probing |
| `channels/twitter.py` | 20 | `.base`, `.utils` | `TwitterChannel` | Twitter/X: curl backend, tier 0 |
| `channels/youtube.py` | 24 | `.base`, `.utils` | `YouTubeChannel` | YouTube: yt-dlp→curl fallback, tier 0 |
| `channels/reddit.py` | 20 | `.base`, `.utils` | `RedditChannel` | Reddit: curl backend, tier 0 |
| `channels/facebook.py` | 20 | `.base`, `.utils` | `FacebookChannel` | Facebook: curl backend, tier 0 |
| `channels/instagram.py` | 20 | `.base`, `.utils` | `InstagramChannel` | Instagram: curl backend, tier 0 |
| `channels/bilibili.py` | 20 | `.base`, `.utils` | `BilibiliChannel` | Bilibili: curl→yt-dlp fallback, tier 0 |
| `channels/xiaohongshu.py` | 26 | `shutil`, `.base`, `.utils` | `XiaoHongShuChannel` | Xiaohongshu/XHS: curl→yt-dlp, **tier 1** |
| `channels/linkedin.py` | 20 | `.base`, `.utils` | `LinkedInChannel` | LinkedIn: curl backend, **tier 1** |
| `channels/v2ex.py` | 20 | `.base`, `.utils` | `V2EXChannel` | V2EX: curl backend, tier 0 |
| `channels/threads.py` | 20 | `.base`, `.utils` | `ThreadsChannel` | Threads (Meta): curl backend, tier 0 |
| `channels/nodeseek.py` | 27 | `.base`, `.utils` | `NodeSeekChannel` | NodeSeek: curl→playwright fallback, tier 0 |
| `channels/nodeloc.py` | 27 | `.base`, `.utils` | `NodeLocChannel` | NodeLoc: curl→playwright fallback, tier 0 |
| `channels/pojie.py` | 27 | `.base`, `.utils` | `PoJieChannel` | 52pojie RE forum: curl→playwright fallback, tier 0 |
| `channels/rss.py` | 22 | `.base`, `.utils` | `RSSChannel` | RSS/Atom feeds: curl backend, tier 0 |
| `channels/web.py` | 20 | `.base`, `.utils` | `WebChannel` | Generic web catch-all: curl, tier 0 |

### dorks/ Directory

| Path | Lines | Imports | Exports | Purpose |
|------|-------|---------|---------|---------|
| `dorks/github_dorks/__init__.py` | 3 | — | `__version__` | Package init (v0.1.1) |
| `dorks/github_dorks/__main__.py` | 5 | `.cli` | `main` | Entrypoint for `python -m github_dorks` |
| `dorks/github_dorks/cli.py` | 225 | `github3`, `os`, `argparse`, `csv`, `time`, `feedparser`, `copy`, `contextlib`, `.github_dorks` | `main`, `search`, `monit`, `metasearch`, `search_wrapper` | GitHub dork CLI: search repos/users for sensitive data patterns, rate-limit aware, CSV export, feed monitoring |

---

## 2. SHELL FILES

**No .sh files found** in the repository.

---

## 3. ENGINE DIRECTORY MAP

### Module Dependency Graph

```
fetch_chain.py (1276 lines) — CORE ENTRY POINT
  ├── phase0.py (700)        — Phase 0: official API routes (15 platforms)
  │   └── curl_cffi, playwright.sync_api (lazy)
  ├── validators.py (349)    — 6-layer response classification
  │   └── bs4 (optional)
  ├── waf_detector.py (214)  — WAF product detection
  │   └── waf_profiles.yaml (223 lines)
  ├── url_transforms.py (120) — 5 URL transforms
  ├── transport.py (310)     — Per-host session pool + SSRF guard
  │   └── safety.py (91)     — IP/redirect safety classification
  ├── executor.py (434)      — Browser fallback routing
  │   ├── templates/nodriver_fetch.py (48)
  │   ├── templates/patchright_fetch.py (49)
  │   └── templates/*.js (Node.js Playwright templates)
  ├── content_safety.py (155) — Prompt-injection detection
  │   └── url_masking.py (70) — URL credential redaction
  ├── learning.py (179)      — U5 self-learning store
  │   └── ~/.novaxinwei/learned.json
  ├── observations_log.py (62) — JSONL fetch observations
  │   └── observations/fetch-YYYY-MM-DD.jsonl
  └── x_search.py (289)      — X/Twitter keyword discovery
      ├── x_search_types.py (42) — XPost, XSearchResult
      └── x_search_io.py (46)    — HTTP + xAI credential
```

### Fetch Chain Phases

| Phase | Module | What It Does |
|-------|--------|--------------|
| Phase 0 | `phase0.py` | Official public API routes for 15 platforms (Reddit RSS/JSON/oembed, X syndication, YouTube yt-dlp, etc.) |
| Phase 1 | `fetch_chain.py` | Probe: single curl_cffi request with default identity |
| Phase 2 | `waf_detector.py` + `fetch_chain.py` | Detect WAF product → build diversity-ordered grid (TLS families × transforms × referers) → execute candidates |
| Phase 3 | `executor.py` | Browser fallback: nodriver/patchright/Playwright Node.js templates |

### Key Design Rules
- **No-Site-Name Rule**: engine/ never hardcodes site names (except phase0.py, which is the SANCTIONED exception)
- **R6 Failure Gate**: on ok=False, `untried_routes` and `must_invoke_playwright_mcp` tell the caller what escalation remains
- **R7 API-first**: when WAF blocks HTML, suggest discovering internal API endpoints via Playwright MCP
- **U5 Self-Learning**: per-host successful route cached in `~/.novaxinwei/learned.json` (TTL 30d, cap 500)

---

## 4. CHANNELS DIRECTORY MAP (15 backends)

| # | Channel | Platform | Backends | Tier | Host Match | Phase 0 Routes |
|---|---------|----------|----------|------|------------|----------------|
| 1 | `TwitterChannel` | X/Twitter | curl | 0 | x.com, twitter.com | tweet-result, oembed, oembed-profile, syndication-timeline |
| 2 | `YouTubeChannel` | YouTube | yt-dlp, curl | 0 | youtube.com, youtu.be | yt-dlp --dump-json |
| 3 | `RedditChannel` | Reddit | curl | 0 | reddit.com, redd.it | .rss, .json, oembed |
| 4 | `FacebookChannel` | Facebook | curl | 0 | facebook.com, fb.com, fb.watch | oembed, html |
| 5 | `InstagramChannel` | Instagram | curl | 0 | instagram.com | oembed, html |
| 6 | `BilibiliChannel` | Bilibili | curl, yt-dlp | 0 | bilibili.com, b23.tv | API (bilibili.com/x/web-interface/view), Playwright |
| 7 | `XiaoHongShuChannel` | Xiaohongshu | curl, yt-dlp | **1** | xiaohongshu.com, xhslink.com | mobile-api (edith.xiaohongshu.com), html |
| 8 | `LinkedInChannel` | LinkedIn | curl | **1** | linkedin.com | oembed (noashare), html, Playwright |
| 9 | `V2EXChannel` | V2EX | curl | 0 | v2ex.com | API (topics/show.json) |
| 10 | `ThreadsChannel` | Threads (Meta) | curl | 0 | threads.net | inline-json (video_versions), meta tags |
| 11 | `NodeSeekChannel` | NodeSeek | curl, playwright | 0 | nodeseek.com | — |
| 12 | `NodeLocChannel` | NodeLoc | curl, playwright | 0 | nodeloc.com | — |
| 13 | `PoJieChannel` | 52pojie.cn | curl, playwright | 0 | 52pojie.cn | — |
| 14 | `RSSChannel` | RSS/Atom | curl | 0 | (path-based: .rss, .xml, /feed, /rss) | — |
| 15 | `WebChannel` | Generic web | curl | 0 | (any http/https) | — |

**Tier meanings**: 0 = zero-config, 1 = needs free key/setup

### Channel Architecture
- `base.py` defines the `Channel` ABC with `can_handle(url)`, `check(config)`, `ordered_backends(config)`
- Each channel module is thin (~20 lines): host matching + backend probing
- `utils.py` provides `host_matches()`, `probe_command()`, `normalize_public_http_url()` (SSRF-safe)
- `__init__.py` registers `ALL_CHANNELS` list and `fetch_parallel()` using `ThreadPoolExecutor`
- Phase 0 routes live in `engine/phase0.py`, not in channel modules

---

## 5. DORKS DIRECTORY MAP

### Data Files

| File | Lines | Format | Contents |
|------|-------|--------|----------|
| `dorks/shodan-dorks.yaml` | 424 | YAML | **126 dork patterns** across 7 categories |
| `dorks/github-dorks.txt` | 141 | Plain text | **127+ dork patterns** (one per line, comments with #) |
| `dorks/github_dorks/` | 3 files | Python | Full GitHub dork CLI with `github3` API integration |

### Shodan Dork Categories (from YAML)
1. **Cameras** (21 patterns): IP webcams, Hikvision, Blue Iris, GeoVision, etc.
2. **Industrial Control Systems** (33 patterns): gas pumps, traffic lights, voting machines, VNC, SCADA protocols (Modbus, S7, BACnet, DNP3, etc.)
3. **Network Infrastructure** (20 patterns): MySQL, MongoDB, Elasticsearch, Docker, Jenkins, Telnet, etc.
4. **Printers** (13 patterns): HP, Samsung, Brother, Epson, Xerox, Canon, OctoPrint
5. **Files and Directories** (9 patterns): open indexes, FTP anonymous access, Samba shares
6. **Compromised Devices** (12 patterns): hacked labels, ransomware, Bitcoin
7. **Miscellaneous** (9 patterns): Ethereum miners, Minecraft servers, North Korea, WordPress

### GitHub Dork CLI
- Uses `github3.py` for API access (search code)
- Reads `github-dorks.txt` patterns
- Supports `--user`, `--repo`, `--monit` (private feed monitoring via `feedparser`)
- Rate-limit aware with automatic sleep on 403
- CSV export via `--outputFile`

---

## 6. OBSERVATIONS DIRECTORY

### What's Tracked
- **File**: `observations/fetch-YYYY-MM-DD.jsonl` (one JSON per line)
- **Current file**: `fetch-2026-09-08.jsonl` (5 entries)
- **Logged by**: `engine/observations_log.py::log_fetch()`

### Schema per entry
```json
{
  "ts": int,                    // Unix timestamp
  "url": "string",              // URL-masked (credentials redacted)
  "domain": "string",           // hostname only
  "ok": bool,                   // final success
  "verdict": "string",          // strong_ok/weak_ok/challenge/etc
  "profile_used": "string|null", // e.g. "phase0:v2ex", "akamai_bot_manager"
  "attempts": int,              // total attempts
  "planned_attempts": int,      // grid planned
  "stop_reason": "string",      // success/exhausted/budget/etc
  "winner": {                   // winning attempt details (if ok)
    "phase": "string",
    "executor": "string",
    "transform": "string",
    "impersonate": "string|null",
    "referer": "string",
    "status": int,
    "body_size": int
  }
}
```

### Current data (5 entries)
- 4× V2EX successful Phase 0 API fetches (v2ex.com/t/956482)
- 1× httpbin.org probe success (curl_cffi safari)

### How observations are used
- **NOT used by learning.py** (learning uses `~/.novaxinwei/learned.json` instead)
- Observations are for **offline analysis** and WAF profile tuning
- Env override: `NOVAXINWEI_OBSERVATIONS_DIR`

---

## 7. CLI ENTRY POINTS & COMMAND ROUTING

### Entry Point 1: `python -m novaxinwei`
- **File**: `__main__.py` → `cli.py::main()`
- **Commands**:

| Command | Function | Description |
|---------|----------|-------------|
| `fetch <url>` | `cmd_fetch()` | Fetch URL through WAF-bypass chain. Options: `--timeout`, `--json`, `--trace`, `--selector`, `--device`, `--no-playwright`, `--no-phase0` |
| `fetch-parallel <urls>` | `cmd_fetch_parallel()` | Parallel fetch via `channels.fetch_parallel()`. Options: `--workers`, `--timeout`, `--json` |
| `dorks shodan <target>` | `_cmd_shodan()` | Shodan dork lookup against `shodan-dorks.yaml`. Options: `--json` |
| `dorks github <query>` | `_cmd_github()` | GitHub dork search against `github-dorks.txt`. Options: `--json` |
| `check` | `cmd_check()` | Check all 15 channel backends availability |

### Entry Point 2: `python3 -m engine`
- **File**: `engine/__main__.py`
- **Commands**: Same `fetch` but with more options: `--max-attempts`, `--no-retry`, `--no-extract`, `--no-markdown`, `--maincontent`, `--no-playwright`, `--no-phase0`

### Entry Point 3: `python -m github_dorks`
- **File**: `dorks/github_dorks/__main__.py` → `dorks/github_dorks/cli.py::main()`
- **Commands**: `-u/--user`, `-r/--repo`, `-d/--dork`, `-m/--monit`, `-o/--outputFile`

### Entry Point 4: `python3 engine/bias_check.py`
- **File**: `engine/bias_check.py`
- **Commands**: `--strict`, `--root`

### Entry Point 5: `python3 engine/x_search.py`
- **File**: `engine/x_search.py::main()`
- **Commands**: `query`, `--limit`, `--timeout`, `--free-only`

---

## 8. ALL DEPENDENCIES

### From `requirements.txt`
| Package | Min Version | Used By |
|---------|-------------|---------|
| `curl_cffi` | ≥0.15.0 | transport.py, phase0.py, x_search_io.py (TLS impersonation) |
| `httpx` | ≥0.27.0 | (available but not actively imported in current code) |
| `feedparser` | ≥6.0 | dorks/github_dorks/cli.py (RSS feed monitoring) |
| `loguru` | ≥0.7 | (available but not actively imported in current code) |
| `rich` | ≥13.0 | (available but not actively imported in current code) |
| `yt-dlp` | ≥2024.1 | phase0.py (_youtube route), channels |
| `pyyaml` | ≥6.0 | waf_detector.py (WAF profile loading), cli.py (shodan dorks) |

### Optional/Soft Dependencies (graceful degradation)
| Package | Used By | What Happens If Missing |
|---------|---------|------------------------|
| `pypdf` | fetch_chain.py | PDF extraction falls through to pdfplumber or raw |
| `pdfplumber` | fetch_chain.py | PDF extraction falls through to pypdf or raw |
| `markdownify` | fetch_chain.py | Raw HTML returned instead of markdown |
| `resiliparse` | fetch_chain.py | Main-content extraction skipped |
| `bs4` (BeautifulSoup) | validators.py | CSS selector matching skipped, returns UNKNOWN |
| `playwright` | phase0.py, executor.py | Browser fallback unavailable |
| `nodriver` | executor.py | Protocol-stealth Chrome unavailable |
| `patchright` | executor.py | Protocol-stealth Chrome unavailable |
| `github3` | dorks/github_dorks/cli.py | GitHub dork CLI unavailable |
| `node`/`npm` | executor.py | Playwright Node.js templates unavailable |

### Implicit/Stdlib Dependencies
`argparse`, `concurrent.futures`, `dataclasses`, `enum`, `functools`, `hashlib`, `html`, `importlib`, `io`, `ipaddress`, `json`, `os`, `pathlib`, `random`, `re`, `shlex`, `shutil`, `socket`, `subprocess`, `sys`, `tempfile`, `threading`, `time`, `urllib.parse`, `copy`, `contextlib`, `csv`

---

## 9. SKILL.md DOCUMENTATION

### Triggers (21)
`novaxinwei`, `web recon`, `fetch url`, `waf bypass`, `dorks`, `shodan dork`, `github dork`, `parallel fetch`, `xiaohongshu`, `bilibili`, `v2ex`, `social media fetch`, `threads`, `nodseek`, `nodloc`, `pojie`

### Capabilities (6)
1. WAF-bypass fetch chain (curl_cffi TLS impersonation + Playwright fallback)
2. 15 Phase 0 API routes (Reddit, X/Twitter, YouTube, Threads, Xiaohongshu, Bilibili, V2EX, Facebook, Instagram, LinkedIn, Cnblogs, CSDN, SegmentFault, SoGitee, Codeberg)
3. 15 social platform channels
4. Shodan + GitHub dork databases
5. Parallel fetch (ThreadPoolExecutor)
6. **No-Site-Name Rule** enforcement (bias_check.py)

### Synergy Section
- NovaXinWei pairs with **Novahaku** (security research skill, 12 domains, 73 modules)
- Workflow: NovaXinWei handles active recon → Novahaku handles vuln discovery/exploitation
- No code-level coupling; data flows through Hermes session context
- Design: both skills are independently usable

---

## 10. EXISTING ENGAGEMENTS DIRECTORY

### Structure
```
D:/Labs/novaxinwei/engagements/
└── synergy-integration/
    ├── BACKUP_MANIFEST.md (834 bytes)
    └── RISK_MATRIX.md (2268 bytes)
```

**Note**: The target directory `engagements/novaxinwei-synergy/` does NOT exist yet. It was created for this INVENTORY.md. The existing `engagements/synergy-integration/` contains prior synergy work.

### Output Format Convention
- Observations go to `observations/fetch-YYYY-MM-DD.jsonl`
- Learning data goes to `~/.novaxinwei/learned.json`
- Engagement docs go to `engagements/<engagement-name>/`
- CLI output: `--json` flag for structured JSON, otherwise human-readable text

---

## SUMMARY STATISTICS

| Metric | Count |
|--------|-------|
| Total .py files | 44 |
| Total .py lines | ~6,400 |
| Total .sh files | 0 |
| Engine modules | 18 (+ 2 template .py) |
| Channel backends | 15 |
| Dork patterns (Shodan) | ~126 (7 categories) |
| Dork patterns (GitHub) | ~127+ (txt file) |
| Phase 0 platforms | 15 |
| CLI entry points | 5 |
| Required packages | 7 |
| Optional packages | 11 |
| WAF profiles | ~10 (in waf_profiles.yaml) |
| URL transforms | 5 |
| Verdict types | 8 |
| Observations entries | 5 |

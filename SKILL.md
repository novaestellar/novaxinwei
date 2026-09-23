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
  - wayback
  - wayai
  - archive
  - historical
  - snapshot
  - common crawl
  - url history
capabilities:
  - WAF-bypass fetch chain (curl_cffi TLS impersonation + Playwright fallback)
  - 15 Phase 0 API routes (Reddit, X/Twitter, YouTube, Threads, Xiaohongshu, Bilibili, V2EX, Facebook, Instagram, LinkedIn, Cnblogs, CSDN, SegmentFault, SoGitee, Codeberg)
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

`python -m novaxinwei` 要求**父目录**在 `sys.path` 上。技能装在 `skills/web/novaxinwei`
时，`cd` 进技能根目录再跑 `-m` 会得到 `No module named novaxinwei` —— 这是 Python `-m`
的正常行为，不是 bug。三种等效入口如下，下文示例默认 CWD 已在父目录，或改用 B/C：

```bash
cd <安装目录>/skills/web                 # A. 从父目录跑 -m
python -m novaxinwei check

cd <安装目录>/skills/web/novaxinwei      # B. 直接跑脚本，任意 CWD 均可
python __main__.py check

export PYTHONPATH=<安装目录>/skills/web  # C. 显式路径，任意 CWD 都能跑 -m
python -m novaxinwei check
```

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
- **GitHub:** 141 dork patterns (10 categories) — curated for automated API search with rate limiting
  - **Extended corpus:** For comprehensive 1400+ GitHub dork keyword reference (manual audit, offline grep), see Novahaku's `testing/references/payloadsallthethings-extras/Insecure Source Code Management/Files/github-dorks.txt`

### 4. Parallel Fetch
```python
from novaxinwei.channels import fetch_parallel
results = fetch_parallel(["url1", "url2", "url3"], max_workers=5)
```

### 5. Engagement Output (New — Synergy with Novahaku)
- Creates `engagements/<target>/` directory structure
- Writes `recon.json` with standardized schema v1.0 (inbound to Novahaku)
- Compatible with Novahaku's engagement reader
```bash
python -m novaxinwei engagement create --target example.com
python -m novaxinwei engagement list
python -m novaxinwei engagement summary --target example.com
```

**Shared root contract.** Both skills resolve `engagements/` the same way:
explicit `base_dir` / `--base-dir` > `NOVAHAKU_ENGAGEMENT_DIR` > `<skill root>/engagements`.
The default is anchored to each skill's own root (never CWD), so both resolve the
same directory no matter where either is launched from. Set
`NOVAHAKU_ENGAGEMENT_DIR` only when engagements live elsewhere — and then set it
for both skills, since a one-sided setting means one side writes where the other
does not read, surfacing as "no results yet" rather than an error. See
`.env.example` § 与 Novahaku 的共享契约.

**Outbound (Novahaku → NovaXinWei).** Novahaku publishes `results.json`
(schema `novaxinwei.results.v1`) plus a flat `results.csv` twin into
`engagements/<target>/`. Read them through `engine/results_reader.py` accessors
rather than parsing raw JSON — they return `None` / empty on missing, corrupt,
binary, non-dict, or `null` payloads. `get_severity_counts` returns **lowercase**
keys (`{"high": 1}`) while `results[].severity` keeps original case (`"High"`).

**Shared ledger.** `chain.json` (schema `novalabs.chain.v1`) records who started
an engagement and who last contributed, so either side going first works. Both
skills implement it independently — never import across skills. `CHAIN_VERSION`
must stay identical on both sides; changing it on one side makes the other treat
the ledger as unreadable.

### 6. CVE Intelligence Tool (New — Synergy with Novahaku)
- **Script:** `tools/cve/cve_scraper.py` — GitHub Security Advisories + HackerOne disclosed reports
- **Auto-export:** `tools/cve/export_to_novahaku.py` — sends feed to Novahaku hunt-cicd cache
- **Consumer:** Novahaku `hunt-cicd` uses this feed for CI/CD exploit context (see novahaku hunt-cicd § CVE Feed)
```bash
python -m novaxinwei tools/cve/cve_scraper.py --ecosystem npm --severity critical
python -m novaxinwei tools/cve/export_to_novahaku.py
```

### 7. Wayback Machine Tool (WayAI — Synergy with Novahaku)
- **Script:** `tools/wayai/wayai.py` — Wayback CDX API + Common Crawl URL harvester
- **Pipeline:** WayAI outputs URLs → Novahaku `secret_scan.py --stdin` scans for 80+ secret patterns
- **Consumer:** Novahaku offensive-osint (see novahaku offensive-osint § Wayback/URL Harvesting)
```bash
python -m novaxinwei wayai example.com | python novahaku/testing/offensive-osint/scripts/secret_scan.py --stdin
```

### 8. GitHub Pages Enumeration Tool (New — Synergy with Novahaku)
- **Script:** `tools/github_pages/github_pages_enum.py` — scan GitHub Pages for private repo content leaks
- **Use case:** Detect `username.github.io/repo-name/` exposing private code/credentials
- **Consumer:** Novahaku consumes findings for exploit workflows
```bash
python -m novaxinwei tools/github_pages/github_pages_enum.py --username victim-org --repos api,secrets,config
```

### 9. Threat Intel Enrichment (Synergy with Novahaku)
- Enriches recon data with DNS, WHOIS, certificate transparency
- 3 levels: basic, enhanced, full
```bash
python -m novaxinwei enrich example.com --level basic
python -m novaxinwei enrich example.com --level enhanced --json
```

## Usage with Hermes

When user asks to:
- "Fetch URL" → use `python -m novaxinwei fetch <url>`
- "Recon target" → use fetch chain + dorks
- "Check social media" → use channel check
- "Parallel fetch" → use `fetch-parallel`
- "Enrich target" → use `python -m novaxinwei enrich <target>`
- "Engagement" → use `python -m novaxinwei engagement create/list/summary`

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

## 🔗 Synergy with Novahaku

NovaXinWei pairs with Novahaku (security research skill, 12 domains, 73 modules) to form a complete recon → exploit chain. Novaxinwei handles active recon (WAF bypass, parallel fetch, dork queries). Novahaku handles vuln discovery, exploitation, and reporting.

**Workflow:**
```
User: "test example.com"
  ↓
1. NovaXinWei — Reconnaissance
   - 15-channel async fetch + WAF bypass
   - Shodan/GitHub dork enumeration
   - Tech stack fingerprinting
   - Output: structured recon (stdout JSON)
  ↓
2. Novahaku — Exploitation
   - Receives recon context via Hermes intent routing
   - Loads matching Hunt Playbooks (54 categories)
   - 63 attack vectors + 14-module web scanner
   - EDR bypass / Pwn Chain / Request Refactoring
```

**Design:** Both skills are independent — NovaXinWei works alone for recon, Novahaku works alone for vuln testing. Hermes routes intent to load both when the user asks for end-to-end testing. No code-level coupling; data flows through Hermes session context.

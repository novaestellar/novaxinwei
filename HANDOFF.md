# HANDOFF.md — NovaXinWei (新信微)

**Version:** 1.0.0
**Date:** 2026-09-07
**Repo:** https://github.com/novaestellar/novaxinwei
**Commit:** 08dea75

---

## What Was Built

NovaXinWei is a web recon engine integrated into Hermes Agent as a skill.
It provides WAF-bypass fetch chain, parallel fetch, dork databases, and 11 social platform channels.

## Architecture

```
novaxinwei/
├── engine/              # WAF-bypass fetch chain (from insane-search)
│   ├── phase0.py        # 10 platform API routes
│   ├── fetch_chain.py   # Core fetch with TLS impersonation
│   ├── validators.py    # 4-layer validation
│   ├── waf_detector.py  # WAF detection
│   └── transport.py     # HTTP transport
├── channels/            # 11 social platform channels (from Agent-Reach)
│   ├── base.py          # Base channel class
│   ├── utils.py         # Shared utilities (URL, text, process)
│   └── {platform}.py    # Per-platform channel
├── dorks/               # Dork databases
│   ├── shodan-dorks.yaml (126 patterns)
│   ├── github-dorks.txt (234 patterns)
│   └── github_dorks/    # CLI for dork execution
├── references/          # 21 API reference docs
├── cli.py               # Unified CLI entry point
├── SKILL.md             # Hermes skill definition
└── requirements.txt     # Dependencies
```

## Usage

```bash
# Check channels
python -m novaxinwei check

# Fetch URL
python -m novaxinwei fetch https://example.com

# Parallel fetch
python -m novaxinwei fetch-parallel url1 url2 url3

# Dork lookup
python -m novaxinwei dorks shodan camera
python -m novaxinwei dorks github password
```

## Integration with NovaHaku

NovaXinWei complements NovaHaku (pentest/exploit skill):
- NovaXinWei = web recon (fetch, dorks, social media)
- NovaHaku = security testing (SQLi, XSS, exploit dev)

## Dependencies

- curl_cffi>=0.15.0 (TLS impersonation)
- httpx>=0.27.0 (HTTP client)
- feedparser>=6.0 (RSS/Atom)
- rich>=13.0 (CLI output)
- yt-dlp>=2024.1 (YouTube extraction)
- pyyaml>=6.0 (dork parsing)

## Known Limitations

- Phase 0 routes use public APIs — no auth required
- Playwright fallback requires Node.js + npm
- Some channels (XHS, LinkedIn) need cookies for full access
- Dork databases are static — update periodically

## Files NOT in Repo

- `NOVASEARCH_INTEGRATION/` (planning docs — local only)
- `TEST_SCRIPT.ps1` (test runner — local only)
- `__pycache__/` (gitignored)

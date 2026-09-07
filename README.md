# NovaXinWei (新信微)

Web recon engine with WAF bypass, parallel fetch, dork databases, and 11 social platform channels.

## Features

- **WAF-Bypass Fetch Chain** — curl_cffi TLS impersonation + Playwright fallback
- **10 Phase 0 API Routes** — Reddit, X, YouTube, Threads, XHS, Bilibili, V2EX, Facebook, Instagram, LinkedIn
- **11 Social Platform Channels** — detect + route URLs automatically
- **Dork Databases** — Shodan (126 patterns) + GitHub (234 patterns)
- **Parallel Fetch** — ThreadPoolExecutor for multi-URL recon

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Check channel availability
python -m novaxinwei check

# Fetch a URL
python -m novaxinwei fetch https://example.com

# Parallel fetch
python -m novaxinwei fetch-parallel url1 url2 url3

# Dork lookup
python -m novaxinwei dorks shodan camera
python -m novaxinwei dorks github password
```

## Structure

```
novaxinwei/
├── __init__.py          # Package init
├── __main__.py          # python -m entry point
├── cli.py               # Unified CLI
├── engine/              # WAF-bypass fetch chain
│   ├── phase0.py        # 10 platform API routes
│   ├── fetch_chain.py   # Core fetch logic
│   ├── validators.py    # 4-layer validation
│   ├── waf_detector.py  # WAF detection
│   ├── transport.py     # HTTP transport
│   └── ...
├── channels/            # 11 social platform channels
│   ├── base.py          # Base channel class
│   ├── utils.py         # Shared utilities
│   └── ...
├── dorks/               # Dork databases
│   ├── shodan-dorks.yaml
│   ├── github-dorks.txt
│   └── github_dorks/
├── references/          # API docs (21 files)
└── SKILL.md             # Hermes skill definition
```

## Usage with Hermes

This skill is designed for Hermes Agent integration. When users request:
- URL fetching → `python -m novaxinwei fetch <url>`
- Web recon → fetch chain + dorks + parallel fetch
- Social media check → channel availability

## License

MIT

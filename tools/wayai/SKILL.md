---
name: wayai
description: Historical URL discovery for a domain from Wayback Machine, Common Crawl, and archive snapshots, de-duplicated and filtered before handing URLs to a fetch or secret-scan stage. Use when reconstructing a target's past attack surface or feeding a recon pipeline with URLs that no longer appear in the live site.
domain: security
category: recon
trigger:
  - wayai
  - wayback
  - archive
  - historical
  - snapshot
  - common crawl
  - url history
auto_load: true
---

# wayai — Wayback Machine & Common Crawl Recon

Passive URL reconnaissance via Wayback Machine CDX API and Common Crawl index. Extract historical URLs, subdomains, and track URL diffs over time.

## Features

- **Wayback Machine:** CDX API query for archived URLs
- **Common Crawl:** Multi-index search for additional coverage
- **Subdomain extraction:** Regex-based subdomain discovery from URLs
- **URL diff tracking:** Compare new vs previous scans
- **HTTP status check:** Verify current URL liveness (optional)
- **Filtering:** Extension-based filtering, parameter-only URLs

## Usage

### Basic Wayback Scan

```bash
python tools/wayai/wayai.py --domain target.com
```

### Wayback + Common Crawl

```bash
python tools/wayai/wayai.py --domain target.com --include-commoncrawl
```

### With Subdomain Extraction

```bash
python tools/wayai/wayai.py --domain target.com --scan-subs
```

### Filter by Extension

```bash
python tools/wayai/wayai.py --domain target.com --exts .php .asp .jsp
```

### Check HTTP Status (Live URLs)

```bash
python tools/wayai/wayai.py --domain target.com --status --threads 50
```

### Date Range Filter

```bash
python tools/wayai/wayai.py --domain target.com --from-date 20200101 --to-date 20231231
```

## Output Files

- `{domain}_all.txt` — All discovered URLs (cumulative)
- `new_urls.txt` — URLs found in current scan not in previous scan
- `subdomains.txt` — Extracted subdomains (with `--scan-subs`)
- `urls_status.csv` — URL, HTTP status, content-length (with `--status`)

## Arguments

```
--domain DOMAIN         Target domain (required)
--from-date YYYYMMDD    Wayback start date
--to-date YYYYMMDD      Wayback end date
--exts EXT [EXT ...]    Filter by extensions (.php, .asp, etc.)
--with-params           Only URLs with query parameters
--include-commoncrawl   Add Common Crawl index results
--status                Check HTTP status of discovered URLs
--scan-subs             Extract subdomains from URLs
--threads N             HTTP status check threads (default: 20)
```

## Integration with NovaXinWei

Auto-loaded when NovaXinWei detects: `wayback`, `archive`, `wayai`, `historical`, `snapshot`, `common crawl`.

**Typical workflow:**
1. NovaXinWei subdomain enum → wayai historical URL discovery
2. wayai URL list → NovaXinWei content scraping
3. Diff tracking for continuous monitoring

## Pitfalls

### Wayback Machine Rate Limiting
- **Symptom:** 429 Too Many Requests or timeouts
- **Mitigation:** Add delays between requests, reduce concurrent connections
- **CDX API limits:** ~15 req/sec sustained; burst to 30 acceptable

### Common Crawl Timeouts
- **Issue:** Index API can be slow (15s default timeout often insufficient)
- **Fix:** Script uses 20s timeout; for large domains, expect 60-120s per index
- **Workaround:** Skip Common Crawl (`--include-commoncrawl` omitted) for speed

### Large Result Sets
- **Memory:** Script uses `OrderedDict` for deduplication — 100K+ URLs may use 50MB+ RAM
- **Disk I/O:** Writing `{domain}_all.txt` blocks; consider streaming for 1M+ URLs

### Subdomain Regex False Positives
- **Pattern:** `([a-z0-9_-]+\.)+{root_domain}`
- **Limitation:** May miss numeric-only subdomains or Unicode variants
- **Edge case:** CDN URLs (cdn123.cloudfront.net) not extracted as target.com subdomains

### HTTP Status Check Bottleneck
- **6s timeout per URL:** Conservative for slow servers, but serial execution of 10K URLs = hours
- **Solution:** Increase `--threads` (default 20 → 100 for fast scans)
- **Tradeoff:** High concurrency may trigger WAF blocks

## API Dependencies

- **Wayback Machine CDX:** `https://web.archive.org/cdx/search/cdx`
- **Common Crawl Index:** `https://index.commoncrawl.org/collinfo.json`

Both APIs are public, no auth required. Wayback respects robots.txt; Common Crawl does not.

## References

- Wayback Machine CDX API: https://github.com/internetarchive/wayback/tree/master/wayback-cdx-server
- Common Crawl Index: https://commoncrawl.org/documentation

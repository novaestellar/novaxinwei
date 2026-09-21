#!/usr/bin/env python3
"""CVE Scraper — GitHub Security Advisories + HackerOne disclosed reports
Author: novalabs
License: MIT
"""
import requests
import json
import os
from datetime import datetime

CACHE_DIR = "cve_cache"

def fetch_github_advisories(ecosystem=None, severity=None):
    """Fetch GitHub Security Advisories via public API"""
    url = "https://api.github.com/advisories"
    params = {"per_page": 100}
    if ecosystem:
        params["ecosystem"] = ecosystem
    if severity:
        params["severity"] = severity
    
    advisories = []
    try:
        r = requests.get(url, params=params, timeout=30)
        r.raise_for_status()
        for adv in r.json():
            advisories.append({
                "cve_id": adv.get("cve_id"),
                "ghsa_id": adv.get("ghsa_id"),
                "summary": adv.get("summary"),
                "severity": adv.get("severity"),
                "published_at": adv.get("published_at"),
                "url": adv.get("html_url"),
                "affected_packages": [p.get("package", {}).get("name") for p in adv.get("vulnerabilities", [])]
            })
    except Exception as e:
        print(f"[!] GitHub Advisories API error: {e}")
    
    return advisories

def fetch_hackerone_disclosed(api_key=None):
    """Fetch HackerOne disclosed reports (requires API key)
    Note: Implementation deferred — requires user H1 API credentials
    """
    if not api_key:
        return []
    
    # HackerOne GraphQL endpoint
    # query { me { disclosed_reports { edges { node { title, severity } } } } }
    # Implementation requires user authentication
    return []

def save_feed(data, filename="cve-feed.json"):
    """Save CVE feed to cache directory"""
    os.makedirs(CACHE_DIR, exist_ok=True)
    path = os.path.join(CACHE_DIR, filename)
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)
    return path

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="CVE scraper for GitHub Advisories + HackerOne")
    parser.add_argument("--ecosystem", help="Filter by ecosystem (npm, pip, rubygems, etc)")
    parser.add_argument("--severity", help="Filter by severity (low, medium, high, critical)")
    parser.add_argument("--h1-api-key", help="HackerOne API key (optional)")
    args = parser.parse_args()
    
    print("[*] Fetching GitHub Security Advisories...")
    advisories = fetch_github_advisories(args.ecosystem, args.severity)
    print(f"[+] Found {len(advisories)} advisories")
    
    h1_reports = fetch_hackerone_disclosed(args.h1_api_key)
    
    feed = {
        "updated_at": datetime.utcnow().isoformat() + "Z",
        "source": "novaxinwei-cve-scraper",
        "github_advisories": advisories,
        "hackerone_disclosed": h1_reports,
        "stats": {
            "github_count": len(advisories),
            "h1_count": len(h1_reports)
        }
    }
    
    path = save_feed(feed)
    print(f"[✓] CVE feed saved: {path}")

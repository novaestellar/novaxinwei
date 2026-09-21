#!/usr/bin/env python3
"""GitHub Pages misconfiguration scanner
Author: novalabs
License: MIT

Scans GitHub Pages URLs to detect private repo content accidentally exposed
via Pages. Use case: organization has private repos with Pages enabled by
mistake, leaking code/credentials via username.github.io/repo-name/
"""
import requests
import argparse
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

def check_page(username, repo, paths=None):
    """Check if GitHub Pages is accessible for a repo"""
    base_url = f"https://{username}.github.io/{repo}/"
    findings = []
    
    # Default paths to check
    if paths is None:
        paths = ["", "index.html", "README.md", "config.json", ".env", "secrets.json"]
    
    for path in paths:
        url = base_url + path
        try:
            r = requests.get(url, timeout=10, allow_redirects=False)
            if r.status_code == 200:
                findings.append({
                    "repo": repo,
                    "url": url,
                    "status": r.status_code,
                    "size": len(r.content),
                    "content_type": r.headers.get("Content-Type", "")
                })
        except requests.RequestException:
            pass
    
    return findings

def enum_pages_parallel(username, repos, max_workers=5):
    """Enumerate GitHub Pages in parallel"""
    all_findings = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(check_page, username, repo): repo for repo in repos}
        for future in as_completed(futures):
            findings = future.result()
            if findings:
                all_findings.extend(findings)
    return all_findings

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="GitHub Pages leak scanner")
    parser.add_argument("--username", required=True, help="GitHub username or org")
    parser.add_argument("--repos", required=True, help="Comma-separated repo names")
    parser.add_argument("--paths", help="Comma-separated paths to check (default: index.html,README.md,config.json)")
    parser.add_argument("--workers", type=int, default=5, help="Parallel workers (default: 5)")
    parser.add_argument("--json", action="store_true", help="Output JSON format")
    args = parser.parse_args()
    
    repos = [r.strip() for r in args.repos.split(",")]
    paths = [p.strip() for p in args.paths.split(",")] if args.paths else None
    
    findings = enum_pages_parallel(args.username, repos, args.workers)
    
    if args.json:
        print(json.dumps(findings, indent=2))
    else:
        if not findings:
            print("[*] No accessible GitHub Pages found")
        for f in findings:
            print(f"[LEAK] {f['url']} ({f['size']} bytes)")

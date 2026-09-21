#!/usr/bin/env python3
"""Auto-export CVE feed to Novahaku engagement cache
Author: novalabs
License: MIT
"""
import os
import shutil
import json
from pathlib import Path

# Detect Novahaku location (prioritize Hermes deployed path)
NOVAHAKU_PATHS = [
    Path.home() / "AppData/Local/hermes/skills/security/novahaku/testing/hunt/hunt-cicd/cache",
    Path("D:/Labs/novahaku/testing/hunt/hunt-cicd/cache"),
]

def find_novahaku_cache():
    """Find Novahaku hunt-cicd cache directory"""
    for path in NOVAHAKU_PATHS:
        if path.parent.exists():  # hunt-cicd exists
            path.mkdir(parents=True, exist_ok=True)
            return path
    return None

def export_cve_feed(source="cve_cache/cve-feed.json"):
    """Export CVE feed to Novahaku cache"""
    if not os.path.exists(source):
        print(f"[!] Source feed not found: {source}")
        print("[!] Run cve_scraper.py first")
        return False
    
    dest_dir = find_novahaku_cache()
    if not dest_dir:
        print("[!] Novahaku hunt-cicd not found")
        print("[!] Expected locations:")
        for p in NOVAHAKU_PATHS:
            print(f"    {p}")
        return False
    
    dest = dest_dir / "cve-feed.json"
    shutil.copy(source, dest)
    
    # Verify
    with open(dest) as f:
        data = json.load(f)
    
    print(f"[✓] Exported to Novahaku: {dest}")
    print(f"[+] GitHub advisories: {data['stats']['github_count']}")
    print(f"[+] HackerOne disclosed: {data['stats']['h1_count']}")
    print(f"[+] Updated: {data['updated_at']}")
    return True

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Export CVE feed to Novahaku")
    parser.add_argument("--source", default="cve_cache/cve-feed.json", help="Source feed path")
    args = parser.parse_args()
    
    success = export_cve_feed(args.source)
    exit(0 if success else 1)

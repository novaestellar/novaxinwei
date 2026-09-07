"""NovaXinWei — web recon with WAF bypass, parallel fetch, and dork databases.

Usage: python -m novaxinwei <command> [args]

Commands:
    fetch <url>                    Fetch URL through WAF-bypass chain
    fetch-parallel <url1> <url2>   Fetch multiple URLs in parallel
    dorks shodan <target>          Shodan dork lookup
    dorks github <query>           GitHub dork search
    check                          Check channel availability
"""
from __future__ import annotations
import sys
from .cli import main

if __name__ == "__main__":
    sys.exit(main())

"""NovaXinWei — web recon with WAF bypass, parallel fetch, and dork databases.

Usage: python __main__.py <command> [args]

Commands:
    fetch <url>                    Fetch URL through WAF-bypass chain
    fetch-parallel <url1> <url2>   Fetch multiple URLs in parallel
    dorks shodan <target>          Shodan dork lookup
    dorks github <query>           GitHub dork search
    check                          Check channel availability
"""
from __future__ import annotations
import sys
import os

# Support both `python -m novaxinwei` (relative) and `python __main__.py` (direct)
_here = os.path.dirname(os.path.abspath(__file__))
_parent = os.path.dirname(_here)
if _parent not in sys.path:
    sys.path.insert(0, _parent)

# When run as `python -m novaxinwei`, relative imports work.
# When run as `python __main__.py` from inside the dir, we need absolute.
try:
    from .cli import main
except ImportError:
    # Direct execution — treat directory as package
    pkg_name = os.path.basename(_here)
    import importlib
    mod = importlib.import_module(f"{pkg_name}.cli")
    main = mod.main

if __name__ == "__main__":
    sys.exit(main())

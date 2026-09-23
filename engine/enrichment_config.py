"""
NovaXinWei Enrichment Configuration

Central place for the constants the enrichment path reads, so a caller can tune
enrichment without editing engine/enrichment.py.

Kept as a module rather than a YAML/JSON file on purpose: the values are read on
every enrichment call and a missing or malformed data file would have to be
handled on each read. A module cannot go missing, and an import error is
immediate and obvious rather than silent.

No cross-skill imports. Stdlib only.
"""

import sys
from typing import Any, Dict, List

# Recognised enrichment levels, cheapest first. Order is meaningful: each level
# includes the work of the levels before it.
ENRICHMENT_LEVELS: List[str] = ["basic", "enhanced", "full"]

# Default level when a caller does not specify one.
DEFAULT_LEVEL = "basic"

# Per-level work, expressed as the names enrich() checks. Keeping this table in
# one place is what lets enrich() stay a sequence of membership tests.
LEVEL_WORK: Dict[str, List[str]] = {
    "basic": ["dns"],
    "enhanced": ["dns", "whois"],
    "full": ["dns", "whois", "certificates"],
}

# Whether a level may reach the network. All false: enrichment is passive and
# runs unattended, so it must not depend on a third-party API being reachable.
# A network-backed enrichment belongs behind an explicit, interactive call.
LEVEL_USES_NETWORK: Dict[str, bool] = {
    "basic": False,
    "enhanced": False,
    "full": False,
}

# Network calls are disabled for all levels. Kept as an explicit flag rather
# than an absence so a future interactive mode can flip it deliberately.
ALLOW_NETWORK_ENRICHMENT = False

# Timeout for any future network-backed intel, in seconds. Unused while
# ALLOW_NETWORK_ENRICHMENT is False.
NETWORK_TIMEOUT_SECONDS = 10

# Output file written by EnrichmentEngine.save_enriched().
ENRICHED_FILENAME = "recon_enriched.json"

# Key path under which enrichment metadata is recorded in the payload.
ENRICHMENT_META_KEY = "enrichment"

# Engine identifier stamped into the metadata block.
ENGINE_ID = "novaxinwei-enrichment-v1"


def normalize_level(level: Any) -> str:
    """Return a valid level, falling back to the default.

    An unknown level is a caller mistake, not a reason to abort an enrichment
    that could still succeed at the default level.
    """
    if isinstance(level, str) and level.strip().lower() in ENRICHMENT_LEVELS:
        return level.strip().lower()
    return DEFAULT_LEVEL


def work_for_level(level: str) -> List[str]:
    """Work items for a level, in order. Unknown levels get the default's work."""
    return list(LEVEL_WORK.get(normalize_level(level), LEVEL_WORK[DEFAULT_LEVEL]))


def level_includes(level: str, item: str) -> bool:
    """True when ``level`` covers ``item``.

    Replaces the hand-written `if level in ("enhanced","full")` chains: adding a
    level must not require finding every one of them.
    """
    return item in work_for_level(level)


def level_uses_network(level: str) -> bool:
    """True when the level would need network access."""
    if not ALLOW_NETWORK_ENRICHMENT:
        return False
    return bool(LEVEL_USES_NETWORK.get(normalize_level(level), False))


def _selftest() -> int:
    """Self-check. Pure constants and pure functions."""
    checks = []
    checks.append(("levels listed", ENRICHMENT_LEVELS == ["basic", "enhanced", "full"]))
    checks.append(("default is valid", DEFAULT_LEVEL in ENRICHMENT_LEVELS))
    checks.append(("every level has work",
                   all(lvl in LEVEL_WORK for lvl in ENRICHMENT_LEVELS)))
    checks.append(("every level has a network flag",
                   all(lvl in LEVEL_USES_NETWORK for lvl in ENRICHMENT_LEVELS)))
    checks.append(("work table names are known",
                   set(w for items in LEVEL_WORK.values() for w in items) ==
                   {"dns", "whois", "certificates"}))

    checks.append(("basic has dns", work_for_level("basic") == ["dns"]))
    checks.append(("enhanced adds whois", work_for_level("enhanced") == ["dns", "whois"]))
    checks.append(("full adds certificates",
                   work_for_level("full") == ["dns", "whois", "certificates"]))
    checks.append(("levels are cumulative",
                   set(work_for_level("basic")) < set(work_for_level("enhanced")) <
                   set(work_for_level("full"))))

    checks.append(("normalize keeps valid", normalize_level("full") == "full"))
    checks.append(("normalize is case-insensitive", normalize_level("FULL") == "full"))
    checks.append(("normalize trims", normalize_level("  enhanced ") == "enhanced"))
    checks.append(("normalize unknown -> default", normalize_level("bogus") == DEFAULT_LEVEL))
    checks.append(("normalize None -> default", normalize_level(None) == DEFAULT_LEVEL))
    checks.append(("normalize int -> default", normalize_level(7) == DEFAULT_LEVEL))

    checks.append(("full includes certificates", level_includes("full", "certificates") is True))
    checks.append(("basic excludes whois", level_includes("basic", "whois") is False))
    checks.append(("enhanced includes whois", level_includes("enhanced", "whois") is True))
    checks.append(("unknown level uses default work", level_includes("bogus", "dns") is True))

    checks.append(("network disabled by default", ALLOW_NETWORK_ENRICHMENT is False))
    checks.append(("network off for every level",
                   all(level_uses_network(l) is False for l in ENRICHMENT_LEVELS)))
    checks.append(("network flag ignores bad level", level_uses_network("bogus") is False))

    checks.append(("filename set", ENRICHED_FILENAME == "recon_enriched.json"))
    checks.append(("meta key set", ENRICHMENT_META_KEY == "enrichment"))
    checks.append(("engine id set", bool(ENGINE_ID)))
    checks.append(("timeout positive", NETWORK_TIMEOUT_SECONDS > 0))

    # A caller mutating the returned list must not corrupt the table.
    work_for_level("basic").append("injected")
    checks.append(("work_for_level returns a copy",
                   work_for_level("basic") == ["dns"]))

    failed = [n for n, ok in checks if not ok]
    for n, ok in checks:
        print(f"  [{'OK' if ok else 'FAIL'}] {n}")
    if failed:
        print(f"[!] enrichment_config selftest: {len(failed)}/{len(checks)} failed: {failed}")
        return 1
    print(f"[+] enrichment_config selftest: {len(checks)}/{len(checks)} checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(_selftest())

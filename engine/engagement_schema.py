"""
NovaXinWei Engagement Schema Validator

Validates a recon payload before it is written to engagements/<target>/recon.json.

Thin layer over engine/recon_schema.py, which is the single source of truth for
the exchange schema. This module adds validation that reports *all* problems at
once instead of stopping at the first, so a caller can fix them in one pass, and
a non-raising contract so a bad payload never crashes a fetch that succeeded.

No cross-skill imports. Stdlib only.

Usage:
    from engine.engagement_schema import validate_recon
    errors = validate_recon(payload)
    if errors:
        for e in errors:
            print(e)
"""

import os
import sys
from typing import Any, Dict, List

# recon_schema.py sits beside this file. Import lazily so this module can be
# validated on its own without a populated sys.path.
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

try:
    from recon_schema import SCHEMA_VERSION  # type: ignore
except ImportError as exc:  # pragma: no cover - only if the file was moved
    # Do not guess a version. A silent fallback would accept a mismatched
    # payload that the real schema rejects, so the validator would green-light
    # data its own reader refuses.
    raise ImportError(
        "recon_schema.py must sit beside engagement_schema.py - it is the source "
        "of truth for SCHEMA_VERSION"
    ) from exc

# Wire-format version. 'version' carries the payload KIND (e.g.
# 'novaxinwei.results.v1'), 'schema_version' the wire format. Both are validated
# when present: a payload whose keys disagree is rejected rather than trusted
# because one of them happens to look right.
WIRE_VERSION = SCHEMA_VERSION


# Fields every recon payload must carry, with the type each must be.
_REQUIRED_TOP = {
    "version": str,
    "target": str,
    "timestamp": str,
    "source": str,
}

# recon.<field> type contract. Mirrors recon_schema.ReconData.
_RECON_TYPES = {
    "subdomains": list,
    "ports": list,
    "tech_stack": dict,
    "waf": dict,
    "endpoints": list,
}

# Optional recon fields: present means typed, absent is fine.
_RECON_OPTIONAL = {
    "origin_ip": (str, type(None)),
    "dns": (dict, type(None)),
    "certificates": (list, type(None)),
    "whois": (dict, type(None)),
}

# Structural bounds for untrusted payloads. json.dump recurses per nesting level,
# so an unbounded document can validate clean and then raise RecursionError at
# write time. Both limits are generous for real recon output.
MAX_DEPTH = 100
MAX_NODES = 200000


def _check_structure(data: Any) -> List[str]:
    """Iteratively bound nesting depth and node count. Never recurses.

    Iterative on purpose: a depth check implemented with recursion would itself
    blow the stack on exactly the input it exists to reject.
    """
    errors: List[str] = []
    stack = [(data, 1)]
    nodes = 0
    deepest = 1
    while stack:
        node, depth = stack.pop()
        nodes += 1
        if depth > deepest:
            deepest = depth
        if nodes > MAX_NODES:
            errors.append(f"payload too large: more than {MAX_NODES} nodes")
            return errors
        if deepest > MAX_DEPTH:
            errors.append(
                f"payload too deeply nested: depth exceeds {MAX_DEPTH} "
                f"(json.dump would recurse that far and fail)"
            )
            return errors
        if isinstance(node, dict):
            for value in node.values():
                stack.append((value, depth + 1))
        elif isinstance(node, (list, tuple)):
            for value in node:
                stack.append((value, depth + 1))
    return errors


def validate_recon(data: Any) -> List[str]:
    """Validate a recon payload. Returns a list of errors, empty when valid.

    Never raises on malformed input - a caller validating untrusted JSON should
    get a report, not a traceback.

    Structure is bounded too. Depth and node count are enforced here because a
    payload that passes type checks can still be hostile: a 1500-deep document
    validated clean and then blew the stack in json.dump, so "validated" did not
    mean "safe to write". Bounds are MAX_DEPTH and MAX_NODES.

    Args:
        data: Parsed JSON payload (usually a dict).

    Returns:
        List of human-readable error strings. Empty list means valid.
    """
    errors: List[str] = []

    if not isinstance(data, dict):
        return [f"payload must be a dict, got {type(data).__name__}"]

    errors.extend(_check_structure(data))

    # Top-level required fields
    for field, expected in _REQUIRED_TOP.items():
        if field not in data:
            errors.append(f"missing required field: {field}")
            continue
        value = data[field]
        if not isinstance(value, expected):
            errors.append(
                f"{field} must be {expected.__name__}, got {type(value).__name__}"
            )
        elif expected is str and not value.strip():
            errors.append(f"{field} must not be empty")

    # Version must match exactly when present and correct-typed. A recon payload
    # is identified by 'version' == WIRE_VERSION; 'schema_version' is the
    # wire-format marker. Validate both when present so one key cannot mask a
    # wrong value in the other.
    version = data.get("version")
    if isinstance(version, str) and version != SCHEMA_VERSION:
        errors.append(
            f"version mismatch: got {version!r}, expected {SCHEMA_VERSION!r}"
        )
    declared = data.get("schema_version")
    if declared is not None and declared != WIRE_VERSION:
        errors.append(
            f"schema_version mismatch: got {declared!r}, expected {WIRE_VERSION!r}"
        )

    # recon block
    recon = data.get("recon")
    if recon is None:
        errors.append("missing required field: recon")
    elif not isinstance(recon, dict):
        errors.append(f"recon must be a dict, got {type(recon).__name__}")
    else:
        for field, expected in _RECON_TYPES.items():
            if field not in recon:
                errors.append(f"missing required field: recon.{field}")
                continue
            if not isinstance(recon[field], expected):
                errors.append(
                    f"recon.{field} must be {expected.__name__}, "
                    f"got {type(recon[field]).__name__}"
                )
        for field, allowed in _RECON_OPTIONAL.items():
            if field in recon and not isinstance(recon[field], allowed):
                names = "/".join(t.__name__ for t in allowed)
                errors.append(
                    f"recon.{field} must be {names}, "
                    f"got {type(recon[field]).__name__}"
                )

    # Optional typed blocks
    for field in ("dorks", "metadata"):
        if field in data and not isinstance(data[field], dict):
            errors.append(f"{field} must be a dict, got {type(data[field]).__name__}")

    return errors


def is_valid(data: Any) -> bool:
    """True when validate_recon reports no errors."""
    return not validate_recon(data)


def _plan_example_valid() -> bool:
    """Validate the recon.json example embedded in INTEGRATION_PLAN.md.

    The plan is what humans copy from, so a stale example silently teaches the
    wrong schema. This extracts the first JSON block under the recon.json
    heading and runs it through validate_recon, which pins the doc to the code.
    Returns True (skip) when the doc cannot be located, so a moved file never
    turns a doc drift into a hard selftest failure.
    """
    import json
    plan = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "engagements", "synergy-integration", "INTEGRATION_PLAN.md",
    )
    try:
        with open(plan, encoding="utf-8") as fh:
            text = fh.read()
    except (IOError, OSError, UnicodeDecodeError):
        return True
    idx = text.find("recon.json v1.0")
    if idx < 0:
        return True
    start = text.find("{", text.find("```json", idx))
    end = text.find("```", start)
    if start < 0 or end < 0:
        return True
    try:
        sample = json.loads(text[start:end])
    except ValueError:
        return False
    return validate_recon(sample) == []


def _selftest() -> int:
    """Self-check. Runs standalone, touches nothing on disk."""
    good = {
        "version": SCHEMA_VERSION,
        "target": "example.com",
        "timestamp": "2026-09-23T00:00:00Z",
        "source": "novaxinwei",
        "recon": {
            "subdomains": [], "ports": [], "tech_stack": {},
            "waf": {"detected": False}, "endpoints": [],
        },
    }
    checks = [
        ("valid payload passes", validate_recon(good) == []),
        ("is_valid agrees", is_valid(good) is True),
        ("non-dict rejected", bool(validate_recon([1, 2]))),
        ("missing target caught",
         any("target" in e for e in validate_recon({**good, "target": None}))),
        ("empty target caught",
         any("target" in e for e in validate_recon({**good, "target": "  "}))),
        ("wrong version caught",
         any("version" in e for e in validate_recon({**good, "version": "9.9"}))),
        ("missing recon caught",
         any("recon" in e for e in validate_recon({k: v for k, v in good.items() if k != "recon"}))),
        ("recon.ports wrong type caught",
         any("ports" in e for e in validate_recon({**good, "recon": {**good["recon"], "ports": "80"}}))),
        ("missing recon field caught",
         any("subdomains" in e for e in validate_recon(
             {**good, "recon": {k: v for k, v in good["recon"].items() if k != "subdomains"}}))),
        ("optional origin_ip None ok",
         validate_recon({**good, "recon": {**good["recon"], "origin_ip": None}}) == []),
        ("optional origin_ip wrong type caught",
         any("origin_ip" in e for e in validate_recon({**good, "recon": {**good["recon"], "origin_ip": 5}}))),
        ("reports all errors not just first",
         len(validate_recon({"recon": "nope"})) >= 4),
        ("never raises on garbage",
         isinstance(validate_recon("not a dict"), list)),
        ("never raises on None", isinstance(validate_recon(None), list)),
        ("INTEGRATION_PLAN example still valid", _plan_example_valid()),
    ]
    failed = [name for name, ok in checks if not ok]
    for name, ok in checks:
        print(f"  [{'OK' if ok else 'FAIL'}] {name}")
    if failed:
        print(f"[!] engagement_schema selftest: {len(checks) - len(failed)}/{len(checks)} failed: {failed}")
        return 1
    print(f"[+] engagement_schema selftest: {len(checks)}/{len(checks)} checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(_selftest())

"""
NovaXinWei Recon Formatter

Renders a recon payload as text, for logs, chat messages, and terminal output
where JSON is unreadable at a glance.

Read-only and side-effect free: it never touches disk and never calls the
network. Anything that can raise has been reduced to a safe default, because
this runs against payloads of unknown shape (a hand-edited cache, an older
schema, a partial write).

No cross-skill imports. Stdlib only.
"""

import json
import sys
from typing import Any, Dict, List, Optional


def _block(payload: Any) -> Dict[str, Any]:
    """Return the recon block, tolerating both a recon block and a full envelope."""
    if not isinstance(payload, dict):
        return {}
    inner = payload.get("recon")
    return inner if isinstance(inner, dict) else payload


def _as_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _as_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def format_tech_stack(tech_stack: Any) -> str:
    """One line per technology. Handles both {"nginx":"1.24"} and ["nginx/1.24"]."""
    if isinstance(tech_stack, dict) and tech_stack:
        return ", ".join(f"{k} {v}" for k, v in sorted(tech_stack.items(), key=lambda kv: str(kv[0])))
    if isinstance(tech_stack, list) and tech_stack:
        return ", ".join(str(t) for t in tech_stack)
    return "none detected"


def format_waf(waf: Any) -> str:
    """WAF as a single readable phrase."""
    data = _as_dict(waf)
    if not data:
        return "not checked"
    if not data.get("detected"):
        return "none detected"
    product = data.get("product")
    return f"{product} (detected)" if product else "detected (product unknown)"


def format_recon(payload: Any, target: Optional[str] = None) -> str:
    """Multi-line human summary of a recon payload.

    Args:
        payload: Recon block or full envelope.
        target: Overrides the target read from the payload.

    Returns:
        Readable text. Never raises, even for a non-dict payload.
    """
    block = _block(payload)
    name = target or (payload.get("target") if isinstance(payload, dict) else None) or "unknown"

    subdomains = _as_list(block.get("subdomains"))
    ports = _as_list(block.get("ports"))
    endpoints = _as_list(block.get("endpoints"))
    dns = _as_dict(block.get("dns"))

    lines = [f"Recon: {name}"]
    lines.append(f"  Subdomains : {len(subdomains)}" + (f" ({', '.join(map(str, subdomains[:5]))}"
                                                        + (" ..." if len(subdomains) > 5 else "") + ")"
                                                        if subdomains else ""))
    lines.append(f"  Ports      : {', '.join(map(str, ports)) if ports else 'none'}")
    lines.append(f"  Tech       : {format_tech_stack(block.get('tech_stack'))}")
    lines.append(f"  WAF        : {format_waf(block.get('waf'))}")
    lines.append(f"  Origin IP  : {block.get('origin_ip') or 'not found'}")
    lines.append(f"  Endpoints  : {len(endpoints)}" + (f" ({', '.join(map(str, endpoints[:5]))}"
                                                        + (" ..." if len(endpoints) > 5 else "") + ")"
                                                        if endpoints else ""))
    if dns:
        ips = _as_list(dns.get("ips"))
        lines.append(f"  DNS IPs    : {', '.join(map(str, ips)) if ips else 'none'}")
    return "\n".join(lines)


def format_findings(payload: Any) -> str:
    """Multi-line summary of Novahaku's results.json. Never raises."""
    data = payload if isinstance(payload, dict) else {}
    results = _as_dict(data.get("results"))
    records = _as_list(results.get("findings"))
    engagement = _as_dict(data.get("engagement"))

    counts: Dict[str, int] = {}
    for rec in records:
        if isinstance(rec, dict):
            sev = str(rec.get("severity", "info")).lower()
            counts[sev] = counts.get(sev, 0) + 1

    lines = [f"Findings: {data.get('target') or 'unknown'}"]
    lines.append(f"  Phase      : {engagement.get('phase') or 'unknown'}")
    lines.append(f"  Total      : {len([r for r in records if isinstance(r, dict)])}")
    lines.append("  By severity: " + (", ".join(f"{k}={v}" for k, v in sorted(counts.items()))
                                      if counts else "none"))
    for rec in records:
        if isinstance(rec, dict):
            lines.append(f"    [{str(rec.get('severity', '?')).upper():<8}] "
                         f"{rec.get('id') or '?'} {rec.get('title') or '(untitled)'}")
    return "\n".join(lines)


def format_conflicts(left: Any, right: Any,
                     left_name: str = "novaxinwei", right_name: str = "novahaku") -> List[str]:
    """Describe fields where two payloads disagree.

    Two sides of one engagement can hold different views of the target (recon
    found three subdomains, testing used two). Surfacing that difference is the
    point - silently preferring one side would hide a real inconsistency.

    Returns a list of human-readable conflict lines; empty when they agree.
    """
    a, b = _block(left), _block(right)
    conflicts: List[str] = []

    for field in ("subdomains", "ports", "endpoints"):
        va, vb = _as_list(a.get(field)), _as_list(b.get(field))
        if va or vb:
            sa, sb = {json.dumps(x, sort_keys=True) for x in va}, {json.dumps(x, sort_keys=True) for x in vb}
            if sa != sb:
                only_a = len(sa - sb)
                only_b = len(sb - sa)
                conflicts.append(
                    f"{field}: {left_name} has {len(sa)}, {right_name} has {len(sb)} "
                    f"({only_a} only in {left_name}, {only_b} only in {right_name})"
                )

    for field in ("origin_ip", "waf"):
        va, vb = a.get(field), b.get(field)
        if isinstance(va, dict) or isinstance(vb, dict):
            if _as_dict(va) != _as_dict(vb):
                conflicts.append(f"{field}: {left_name}={va!r} vs {right_name}={vb!r}")
        elif va != vb and (va is not None or vb is not None):
            conflicts.append(f"{field}: {left_name}={va!r} vs {right_name}={vb!r}")

    return conflicts


def _selftest() -> int:
    """Self-check. Pure functions only, so nothing touches disk."""
    checks = []

    sample = {
        "version": "1.0", "target": "fmt.example",
        "recon": {
            "subdomains": ["a.fmt.example", "b.fmt.example"],
            "ports": [80, 443],
            "tech_stack": {"nginx": "1.24", "php": "8.1"},
            "waf": {"detected": True, "product": "Cloudflare"},
            "origin_ip": "203.0.113.9",
            "endpoints": ["/api", "/admin"],
            "dns": {"ips": ["203.0.113.9"]},
        },
    }

    text = format_recon(sample)
    checks.append(("recon shows target", "fmt.example" in text))
    checks.append(("recon shows subdomain count", "Subdomains : 2" in text))
    checks.append(("recon shows ports", "80, 443" in text))
    checks.append(("recon shows tech", "nginx 1.24" in text))
    checks.append(("recon shows waf", "Cloudflare" in text))
    checks.append(("recon shows origin", "203.0.113.9" in text))
    checks.append(("recon shows endpoints", "Endpoints  : 2" in text))
    checks.append(("recon shows dns", "DNS IPs" in text))

    # Also accepts a bare recon block, not just a full envelope.
    bare = format_recon(sample["recon"], target="bare.example")
    checks.append(("accepts bare recon block", "bare.example" in bare and "Cloudflare" in bare))

    # Empty and malformed inputs never raise.
    checks.append(("empty payload safe", "unknown" in format_recon(None)))
    checks.append(("non-dict payload safe", "unknown" in format_recon("junk")))
    checks.append(("empty dict safe", "none detected" in format_recon({})))
    checks.append(("list payload safe", isinstance(format_recon([1, 2]), str)))
    checks.append(("int payload safe", isinstance(format_recon(42), str)))

    # Wrong types inside: degrade, do not raise.
    bad = {"recon": {"subdomains": "not-a-list", "ports": 7, "tech_stack": 3,
                     "waf": "nope", "endpoints": {"a": 1}, "dns": []}}
    checks.append(("wrong-type fields safe", isinstance(format_recon(bad), str)))
    checks.append(("wrong-type subdomains -> 0", "Subdomains : 0" in format_recon(bad)))
    checks.append(("wrong-type ports -> none", "none" in format_recon(bad)))

    # Individual formatters.
    checks.append(("tech dict formatted",
                   format_tech_stack({"nginx": "1.24"}) == "nginx 1.24"))
    checks.append(("tech list formatted", "nginx/1.24" in format_tech_stack(["nginx/1.24"])))
    checks.append(("tech empty -> none", format_tech_stack({}) == "none detected"))
    checks.append(("tech wrong type -> none", format_tech_stack(5) == "none detected"))
    checks.append(("waf undetected", format_waf({"detected": False}) == "none detected"))
    checks.append(("waf detected w/ product", format_waf({"detected": True, "product": "X"}) == "X (detected)"))
    checks.append(("waf detected no product", "product unknown" in format_waf({"detected": True})))
    checks.append(("waf not checked", format_waf({}) == "not checked"))
    checks.append(("waf wrong type", format_waf(None) == "not checked"))

    # Findings formatter, including on Novahaku's real envelope shape.
    findings = {
        "target": "fmt.example",
        "engagement": {"phase": "report"},
        "results": {"findings": [
            {"id": "F-001", "title": "Missing header", "severity": "High"},
            {"id": "F-002", "title": "Banner disclosure", "severity": "low"},
            "junk", None,
        ]},
    }
    text2 = format_findings(findings)
    checks.append(("findings shows phase", "report" in text2))
    checks.append(("findings counts dicts only", "Total      : 2" in text2))
    checks.append(("findings uppercases severity", "[HIGH" in text2))
    checks.append(("findings by-severity line", "high=1" in text2 and "low=1" in text2))
    checks.append(("findings skips junk", "junk" not in text2))
    checks.append(("findings empty safe", "Total      : 0" in format_findings({})))
    checks.append(("findings None safe", isinstance(format_findings(None), str)))

    # Conflict detection.
    left = {"recon": {"subdomains": ["a", "b"], "ports": [80], "origin_ip": "1.1.1.1"}}
    right = {"recon": {"subdomains": ["a"], "ports": [80], "origin_ip": "1.1.1.1"}}
    conflicts = format_conflicts(left, right)
    checks.append(("conflict detects subdomain drift", any("subdomains" in c for c in conflicts)))
    checks.append(("conflict ignores identical ports", not any("ports" in c for c in conflicts)))
    checks.append(("conflict ignores identical origin", not any("origin_ip" in c for c in conflicts)))
    checks.append(("conflict names both sides",
                   any("novaxinwei" in c and "novahaku" in c for c in conflicts)))
    checks.append(("identical payloads -> no conflicts",
                   format_conflicts(left, left) == []))
    checks.append(("conflict on origin difference",
                   any("origin_ip" in c for c in format_conflicts(
                       {"recon": {"origin_ip": "1.1.1.1"}}, {"recon": {"origin_ip": "2.2.2.2"}}))))
    checks.append(("conflict safe on junk", format_conflicts(None, "junk") == []))
    checks.append(("conflict on waf difference",
                   any("waf" in c for c in format_conflicts(
                       {"recon": {"waf": {"detected": True}}},
                       {"recon": {"waf": {"detected": False}}}))))

    failed = [n for n, ok in checks if not ok]
    for n, ok in checks:
        print(f"  [{'OK' if ok else 'FAIL'}] {n}")
    if failed:
        print(f"[!] recon_formatter selftest: {len(failed)}/{len(checks)} failed: {failed}")
        return 1
    print(f"[+] recon_formatter selftest: {len(checks)}/{len(checks)} checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(_selftest())

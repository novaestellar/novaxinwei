"""
NovaXinWei Threat Intel

Adds offline, deterministic signals about a target: which risky technology
versions are in play, whether the target is exposed in ways that attract
opportunistic scanning, and what a defender would want to know first.

Deliberately offline. Recon already touches the target; a second round of
unauthenticated calls to third-party APIs (crt.sh, WHOIS, Shodan) during a run
adds latency, rate-limit failures, and a paper trail on the target domain
without changing what the engagement can conclude. Everything below is derived
from data already on disk. Network-backed intel belongs in a separate, explicit
call - not in the passive enrichment path.

Findings here are *leads*, not vulnerabilities. Each carries a confidence and a
reason so a human can discard it quickly.

No cross-skill imports. Stdlib only.
"""

import datetime
import json
import os
import re
import sys
from typing import Any, Dict, List, Optional

INTEL_VERSION = "novalabs.threat_intel.v1"

# Technology -> minimum version considered acceptable. Anything below is a lead.
# Deliberately conservative and short: a long stale table generates noise, and
# noise is what makes an operator stop reading the output.
TECH_RISK_TABLE: Dict[str, Dict[str, Any]] = {
    "php": {"below": (7, 4), "severity": "high",
            "reason": "PHP below 7.4 is end-of-life and receives no security fixes"},
    "nginx": {"below": (1, 20), "severity": "medium",
              "reason": "nginx below 1.20 predates several HTTP/2 and resolver fixes"},
    "apache": {"below": (2, 4), "severity": "medium",
               "reason": "Apache below 2.4.x predates current mod_* fixes"},
    "wordpress": {"below": (6, 0), "severity": "high",
                  "reason": "WordPress below 6.0 is outside the maintained branch"},
    "jquery": {"below": (3, 5), "severity": "medium",
               "reason": "jQuery below 3.5 has known XSS issues in DOM helpers"},
    "openssl": {"below": (1, 1, 1), "severity": "high",
                "reason": "OpenSSL below 1.1.1 lacks TLS 1.3 and current CVE fixes"},
    "drupal": {"below": (9, 0), "severity": "high",
               "reason": "Drupal 7/8 are end-of-life"},
    "joomla": {"below": (4, 0), "severity": "high",
              "reason": "Joomla 3.x is end-of-life"},
}

# Header presence that materially reduces opportunistic exposure. Absence is
# reported as a lead; the point is to know whether the basics are in place.
HARDENING_HEADERS = {
    "strict-transport-security": "HSTS missing; downgrade to HTTP is not prevented",
    "content-security-policy": "No CSP; injection impact is not constrained",
    "x-content-type-options": "No nosniff; MIME confusion is possible",
    "x-frame-options": "No frame protection and no CSP frame-ancestors",
}

# Paths that suggest sensitive surface reachable without authentication.
SENSITIVE_PATH_HINTS = (
    ".git", ".env", ".svn", "backup", "db.sql", "dump", "phpinfo",
    "adminer", "phpmyadmin", "swagger", "actuator", "server-status",
    ".ds_store", "web.config", "id_rsa",
)


def _parse_version(text: Any) -> Optional[tuple]:
    """Extract the leading numeric version tuple from a banner.

    Returns None when no version is discernible - an unknown version is not
    treated as vulnerable, because guessing here produces pure noise.

    >>> _parse_version("nginx/1.18.0")
    (1, 18, 0)
    >>> _parse_version("no version here") is None
    True
    """
    if text is None:
        return None
    match = re.search(r"(\d+)\.(\d+)(?:\.(\d+))?", str(text))
    if not match:
        return None
    parts = tuple(int(g) for g in match.groups() if g is not None)
    return parts


def _below(actual: tuple, minimum: tuple) -> bool:
    """Compare padded tuples so (1,18) and (1,18,0) agree."""
    width = max(len(actual), len(minimum))
    a = actual + (0,) * (width - len(actual))
    b = minimum + (0,) * (width - len(minimum))
    return a < b


def tech_risk_leads(target: str, recon: Optional[Dict[str, Any]] = None,
                    data: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Risky technology versions present in the recon payload.

    Accepts either a recon block or a full envelope; callers exist on both sides
    of this integration and should not have to remember which.
    """
    body = recon if isinstance(recon, dict) else (data if isinstance(data, dict) else {})
    block = body.get("recon") if isinstance(body.get("recon"), dict) else body
    stack = block.get("tech_stack") if isinstance(block.get("tech_stack"), list) or \
        isinstance(block.get("tech_stack"), dict) else {}

    # Normalise: tech_stack may be {"nginx": "1.18"} or ["nginx/1.18"].
    pairs: List[tuple] = []
    if isinstance(stack, dict):
        pairs = [(str(k), v) for k, v in stack.items()]
    elif isinstance(stack, list):
        for item in stack:
            if isinstance(item, dict):
                for k, v in item.items():
                    pairs.append((str(k), v))
            elif isinstance(item, str) and "/" in item:
                # "php/5.6" - the name and version share one string, so split
                # them. Handing the whole string through as both name and banner
                # would never match the risk table.
                name, _, banner = item.partition("/")
                pairs.append((name, banner))
            else:
                pairs.append((str(item), item))

    leads: List[Dict[str, Any]] = []
    for name, banner in pairs:
        key = name.strip().lower()
        rule = TECH_RISK_TABLE.get(key)
        if not rule:
            continue
        version = _parse_version(banner)
        if version is None:
            continue
        if _below(version, rule["below"]):
            leads.append({
                "kind": "outdated_technology",
                "technology": key,
                "version": ".".join(str(p) for p in version),
                "minimum_recommended": ".".join(str(p) for p in rule["below"]),
                "severity": rule["severity"],
                "confidence": "confirmed",
                "target": target,
                "reason": rule["reason"],
                "source": "tech_stack",
            })
    return leads


def hardening_leads(target: str, recon: Optional[Dict[str, Any]] = None,
                    data: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Missing defensive headers, only when the payload actually carries headers.

    If no header data was collected, reporting every header as missing would be
    a false claim about the target. Absent evidence is not evidence.
    """
    body = recon if isinstance(recon, dict) else (data if isinstance(data, dict) else {})
    block = body.get("recon") if isinstance(body.get("recon"), dict) else body
    headers = block.get("headers")
    if not isinstance(headers, dict) or not headers:
        return []

    present = {str(k).strip().lower() for k in headers}
    leads = []
    for header, why in HARDENING_HEADERS.items():
        if header not in present:
            leads.append({
                "kind": "missing_hardening_header",
                "header": header,
                "severity": "low",
                "confidence": "confirmed",
                "target": target,
                "reason": why,
                "source": "headers",
            })
    return leads


def exposure_leads(target: str, recon: Optional[Dict[str, Any]] = None,
                   data: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Endpoints whose path suggests sensitive or administrative surface."""
    body = recon if isinstance(recon, dict) else (data if isinstance(data, dict) else {})
    block = body.get("recon") if isinstance(body.get("recon"), dict) else body
    endpoints = block.get("endpoints")
    if not isinstance(endpoints, list):
        return []

    leads = []
    for raw in endpoints:
        if not isinstance(raw, str):
            continue
        lowered = raw.lower()
        for hint in SENSITIVE_PATH_HINTS:
            if hint in lowered:
                leads.append({
                    "kind": "sensitive_path_exposed",
                    "endpoint": raw,
                    "matched": hint,
                    "severity": "medium",
                    "confidence": "possible",
                    "target": target,
                    "reason": f"Path contains '{hint}'; verify it is not "
                              f"reachable without authentication",
                    "source": "endpoints",
                })
                break
    return leads


def intel_summary(target: str, recon: Optional[Dict[str, Any]] = None,
                  data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """All leads plus counts, in one structure."""
    leads = (tech_risk_leads(target, recon, data)
             + hardening_leads(target, recon, data)
             + exposure_leads(target, recon, data))
    by_severity: Dict[str, int] = {}
    for lead in leads:
        sev = str(lead.get("severity", "info")).lower()
        by_severity[sev] = by_severity.get(sev, 0) + 1
    return {
        "version": INTEL_VERSION,
        "target": target,
        "timestamp": datetime.datetime.now(datetime.timezone.utc)
        .strftime("%Y-%m-%dT%H:%M:%SZ"),
        "leads": leads,
        "counts": {"total": len(leads), "by_severity": by_severity},
        "note": "Leads require verification before being reported as findings.",
    }


def _default_root() -> str:
    """Shared engagements root: NOVAHAKU_ENGAGEMENT_DIR, else ./engagements.

    Same precedence as chain_state._default_root and engagement_output. Both
    readers here used os.getcwd() only, so with the env var set they resolved a
    different root than the writer and reported a real engagement as having no
    recon - silently returning an empty intel summary instead of an error.
    """
    env = os.environ.get("NOVAHAKU_ENGAGEMENT_DIR", "").strip()
    return os.path.abspath(env) if env else os.path.join(os.getcwd(), "engagements")


def enrich_with_intel(target: str, base_dir: Optional[str] = None) -> Dict[str, Any]:
    """Read recon.json for target and return an intel summary. Never raises.

    Returns an empty summary with a reason when there is no recon to work from,
    so a caller can always consume the result.
    """
    root = os.path.abspath(base_dir) if base_dir else _default_root()
    path = os.path.join(root, target, "recon.json")
    payload = None
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                loaded = json.load(fh)
            payload = loaded if isinstance(loaded, dict) else None
        except (json.JSONDecodeError, IOError, UnicodeDecodeError, ValueError):
            payload = None

    if payload is None:
        return {
            "version": INTEL_VERSION,
            "target": target,
            "timestamp": datetime.datetime.now(datetime.timezone.utc)
            .strftime("%Y-%m-%dT%H:%M:%SZ"),
            "leads": [],
            "counts": {"total": 0, "by_severity": {}},
            "note": "No readable recon.json; nothing to analyse.",
        }
    return intel_summary(target, payload)


def save_intel(target: str, summary: Dict[str, Any],
               base_dir: Optional[str] = None) -> Optional[str]:
    """Write intel.json alongside recon.json. Atomic; None when it cannot write."""
    root = os.path.abspath(base_dir) if base_dir else _default_root()
    edir = os.path.join(root, target)
    if not os.path.isdir(edir):
        return None
    out = os.path.join(edir, "intel.json")
    tmp = out + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(summary, fh, indent=2, ensure_ascii=False)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, out)
    except IOError:
        return None
    return out


def _selftest() -> int:
    """Self-check in a temp dir. Touches nothing real."""
    import shutil
    import tempfile

    checks = []
    base = tempfile.mkdtemp(prefix="novaxinwei-intel-selftest-")
    try:
        # Version parsing.
        checks.append(("parse nginx banner", _parse_version("nginx/1.18.0") == (1, 18, 0)))
        checks.append(("parse bare version", _parse_version("1.2") == (1, 2)))
        checks.append(("parse no version -> None", _parse_version("apache") is None))
        checks.append(("parse None -> None", _parse_version(None) is None))
        checks.append(("parse junk -> None", _parse_version("no version here") is None))
        checks.append(("(1,18) below (1,20)", _below((1, 18), (1, 20)) is True))
        checks.append(("(1,20) not below (1,20)", _below((1, 20), (1, 20)) is False))
        checks.append(("padded compare agrees", _below((1, 18), (1, 20, 0)) is True))
        checks.append(("(1,18,0) below (1,20)", _below((1, 18, 0), (1, 20)) is True))

        # Outdated tech, dict form.
        recon = {"recon": {"tech_stack": {"php": "5.6", "nginx": "1.24", "unknown": "1.0"}}}
        leads = tech_risk_leads("t.example", recon)
        checks.append(("old php flagged", any(l["technology"] == "php" for l in leads)))
        checks.append(("current nginx NOT flagged",
                       not any(l["technology"] == "nginx" for l in leads)))
        checks.append(("unknown tech ignored",
                       not any(l["technology"] == "unknown" for l in leads)))
        php = next((l for l in leads if l["technology"] == "php"), {})
        checks.append(("lead carries severity", php.get("severity") == "high"))
        checks.append(("lead carries reason", bool(php.get("reason"))))
        checks.append(("lead carries minimum", php.get("minimum_recommended") == "7.4"))
        checks.append(("lead is marked a lead", php.get("kind") == "outdated_technology"))

        # List form of tech_stack.
        leads2 = tech_risk_leads("t.example", {"recon": {"tech_stack": ["php/5.6"]}})
        checks.append(("list tech_stack handled", any(l["technology"] == "php" for l in leads2)))

        # Full envelope accepted (no "recon" wrapper needed).
        leads3 = tech_risk_leads("t.example", None,
                                 {"recon": {"tech_stack": {"php": "5.6"}}})
        checks.append(("data= kwarg works", len(leads3) >= 1))

        # Unknown version must not be flagged.
        leads4 = tech_risk_leads("t.example", {"recon": {"tech_stack": {"php": "unknown"}}})
        checks.append(("unversioned tech not flagged", leads4 == []))

        # Headers: absent header data must produce NO claims.
        checks.append(("no headers -> no leads",
                       hardening_leads("t.example", {"recon": {}}) == []))
        checks.append(("headers present -> leads",
                       len(hardening_leads("t.example", {
                           "recon": {"headers": {"server": "nginx"}}})) == 4))
        checks.append(("declared header not reported",
                       not any(l["header"] == "server" for l in hardening_leads(
                           "t.example", {"recon": {"headers": {"server": "nginx"}}}))))
        checks.append(("header case-insensitive",
                       len([l for l in hardening_leads("t.example", {
                           "recon": {"headers": {"Strict-Transport-Security": "max-age=1"}}})
                           if l["header"] == "strict-transport-security"]) == 0))

        # Exposure.
        exp = exposure_leads("t.example", {"recon": {
            "endpoints": ["/api/users", "/.git/config", "/adminer.php", "/health"]}})
        checks.append(("sensitive paths flagged", len(exp) == 2))
        checks.append(("clean path not flagged",
                       not any(l["endpoint"] == "/health" for l in exp)))
        checks.append(("non-string endpoint skipped",
                       exposure_leads("t.example", {"recon": {"endpoints": [None, 1]}}) == []))
        checks.append(("missing endpoints -> []",
                       exposure_leads("t.example", {"recon": {}}) == []))

        # Summary.
        summary = intel_summary("t.example", {"recon": {
            "tech_stack": {"php": "5.6"}, "headers": {"server": "nginx"},
            "endpoints": ["/.git/config"]}})
        checks.append(("summary version stamped", summary["version"] == INTEL_VERSION))
        checks.append(("summary counts total", summary["counts"]["total"] == len(summary["leads"])))
        checks.append(("summary counts by severity",
                       summary["counts"]["by_severity"].get("high", 0) >= 1))
        checks.append(("summary states leads not findings", "verification" in summary["note"].lower()))

        # enrich_with_intel on a real directory.
        edir = os.path.join(base, "intel.example")
        os.makedirs(edir, exist_ok=True)
        with open(os.path.join(edir, "recon.json"), "w", encoding="utf-8") as fh:
            json.dump({"version": "1.0", "target": "intel.example",
                       "recon": {"tech_stack": {"php": "5.6"}}}, fh)
        import tempfile as _tf
        env_root = _tf.mkdtemp(prefix="novaxinwei-intel-env-")
        _old = os.environ.get("NOVAHAKU_ENGAGEMENT_DIR")
        try:
            os.environ["NOVAHAKU_ENGAGEMENT_DIR"] = env_root
            checks.append(("env var selects root",
                           _default_root() == os.path.abspath(env_root)))
            del os.environ["NOVAHAKU_ENGAGEMENT_DIR"]
            checks.append(("absent env falls back to cwd",
                           _default_root() == os.path.join(os.getcwd(), "engagements")))
        finally:
            if _old is not None:
                os.environ["NOVAHAKU_ENGAGEMENT_DIR"] = _old
            else:
                os.environ.pop("NOVAHAKU_ENGAGEMENT_DIR", None)
            import shutil as _sh
            _sh.rmtree(env_root, ignore_errors=True)

        got = enrich_with_intel("intel.example", base)
        checks.append(("enrich_with_intel reads disk", got["counts"]["total"] >= 1))
        checks.append(("enrich_with_intel saves", save_intel("intel.example", got, base) is not None))
        checks.append(("intel.json on disk",
                       os.path.exists(os.path.join(edir, "intel.json"))))

        # Missing recon -> empty summary, not a crash.
        missing = enrich_with_intel("absent.example", base)
        checks.append(("absent recon -> empty leads", missing["leads"] == []))
        checks.append(("absent recon -> note", "No readable" in missing["note"]))

        # Corrupt recon -> empty summary, not a crash.
        with open(os.path.join(edir, "recon.json"), "w", encoding="utf-8") as fh:
            fh.write("{broken")
        checks.append(("corrupt recon -> empty leads",
                       enrich_with_intel("intel.example", base)["leads"] == []))

        # Binary recon -> empty summary, not a crash.
        with open(os.path.join(edir, "recon.json"), "wb") as fh:
            fh.write(bytes([0xFF, 0xFE, 0x00, 0x01]))
        checks.append(("binary recon -> empty leads",
                       enrich_with_intel("intel.example", base)["leads"] == []))

        # Array recon -> empty summary, not a crash.
        with open(os.path.join(edir, "recon.json"), "w", encoding="utf-8") as fh:
            fh.write("[1,2,3]")
        checks.append(("array recon -> empty leads",
                       enrich_with_intel("intel.example", base)["leads"] == []))

        # save_intel on a missing engagement returns None rather than creating it.
        checks.append(("save_intel refuses missing dir",
                       save_intel("nope.example", summary, base) is None))

        # No .tmp leftover.
        leftovers = [f for f in os.listdir(edir) if f.endswith(".tmp")]
        checks.append(("no .tmp leftover", not leftovers))
    finally:
        shutil.rmtree(base, ignore_errors=True)

    failed = [n for n, ok in checks if not ok]
    for n, ok in checks:
        print(f"  [{'OK' if ok else 'FAIL'}] {n}")
    if failed:
        print(f"[!] threat_intel selftest: {len(failed)}/{len(checks)} failed: {failed}")
        return 1
    print(f"[+] threat_intel selftest: {len(checks)}/{len(checks)} checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(_selftest())

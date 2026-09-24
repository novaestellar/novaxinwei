"""
NovaXinWei Threat Intel Enrichment Engine

Enriches recon.json with additional threat intelligence data.
Designed for Novahaku to consume.

Usage:
    from engine.enrichment import EnrichmentEngine
    engine = EnrichmentEngine()
    enriched = engine.enrich("example.com")
"""

import json
import os
import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path

try:
    import socket
    HAS_SOCKET = True
except ImportError:
    HAS_SOCKET = False


def _default_root() -> Path:
    """Shared engagements root: NOVAHAKU_ENGAGEMENT_DIR, else <skill root>/engagements.

    Same precedence as chain_state._default_root and engagement_output. This
    engine's default was a bare Path("engagements"), so it ignored the env var
    the rest of the repo honours and enriched into a different root than the one
    recon was written to - the CLI then reported success on an empty result.
    The bare Path was also CWD-relative, so two skills launched from different
    directories resolved different roots; the skill root anchor removes CWD
    from the equation entirely.
    """
    env = os.environ.get("NOVAHAKU_ENGAGEMENT_DIR", "").strip()
    if env:
        return Path(env).resolve()
    return Path(__file__).resolve().parent.parent / "engagements"


class EnrichmentEngine:
    """Enriches recon data with threat intelligence."""

    def __init__(self, engagements_dir: str = None):
        """
        Initialize enrichment engine.

        Args:
            engagements_dir: Base engagements directory
        """
        self.engagements_dir = Path(engagements_dir) if engagements_dir else _default_root()

    def enrich(self, target: str, level: str = "basic") -> Dict[str, Any]:
        """
        Enrich recon data for target.

        Args:
            target: Target domain
            level: Enrichment level (basic/enhanced/full)

        Returns:
            Enriched recon dictionary
        """
        recon_path = self.engagements_dir / target / "recon.json"

        if not recon_path.exists():
            return {"error": f"No recon data found for {target}"}

        with open(recon_path, "r", encoding="utf-8") as f:
            recon_data = json.load(f)

        enriched = recon_data.copy()
        enrichment_timestamp = datetime.datetime.utcnow().isoformat() + "Z"

        # Basic enrichment: DNS reverse lookup
        if level in ("basic", "enhanced", "full"):
            enriched = self._enrich_dns(enriched, target)

        # Enhanced enrichment: WHOIS data
        if level in ("enhanced", "full"):
            enriched = self._enrich_whois(enriched, target)

        # Full enrichment: Certificate transparency
        if level == "full":
            enriched = self._enrich_certificates(enriched, target)

        # Update metadata
        if "metadata" not in enriched:
            enriched["metadata"] = {}

        enriched["metadata"]["enrichment"] = {
            "level": level,
            "timestamp": enrichment_timestamp,
            "engine": "novaxinwei-enrichment-v1",
        }

        return enriched

    def _enrich_dns(self, data: Dict[str, Any], target: str) -> Dict[str, Any]:
        """Add DNS information to recon data."""
        if "recon" not in data:
            data["recon"] = {}

        dns_info = {
            "target": target,
            "resolved": True,
            "nameservers": [],
        }

        # Try to resolve the target
        if HAS_SOCKET:
            try:
                ips = socket.getaddrinfo(target, None)
                dns_info["ips"] = list(set(addr[4][0] for addr in ips))
            except socket.gaierror:
                dns_info["resolved"] = False

        data["recon"]["dns"] = dns_info
        return data

    def _enrich_whois(self, data: Dict[str, Any], target: str) -> Dict[str, Any]:
        """Add WHOIS data to recon data."""
        if "recon" not in data:
            data["recon"] = {}

        # WHOIS data would require external API or library
        # For now, add placeholder structure
        whois_info = {
            "target": target,
            "registrar": None,
            "creation_date": None,
            "expiration_date": None,
            "name_servers": [],
            "status": [],
            "note": "WHOIS enrichment requires external API integration",
        }

        data["recon"]["whois"] = whois_info
        return data

    def _enrich_certificates(self, data: Dict[str, Any], target: str) -> Dict[str, Any]:
        """Add certificate transparency data to recon data."""
        if "recon" not in data:
            data["recon"] = {}

        # CT data would require external API (crt.sh, etc.)
        # For now, add placeholder structure
        ct_info = {
            "target": target,
            "certificates": [],
            "note": "Certificate transparency enrichment requires external API integration",
        }

        data["recon"]["certificates"] = ct_info
        return data

    def save_enriched(self, target: str, enriched_data: Dict[str, Any]) -> Path:
        """
        Save enriched recon data back to engagement directory.

        Args:
            target: Target domain
            enriched_data: Enriched recon data

        Returns:
            Path to enriched recon file
        """
        engagement_dir = self.engagements_dir / target
        engagement_dir.mkdir(parents=True, exist_ok=True)

        enriched_path = engagement_dir / "recon_enriched.json"
        with open(enriched_path, "w", encoding="utf-8") as f:
            json.dump(enriched_data, f, indent=2, ensure_ascii=False)

        return enriched_path


def enrich_target(target: str, level: str = "basic",
                  engagements_dir: str = None) -> Dict[str, Any]:
    """
    Convenience function to enrich a target.

    Args:
        target: Target domain
        level: Enrichment level
        engagements_dir: Base engagements directory

    Returns:
        Enriched recon dictionary
    """
    engine = EnrichmentEngine(engagements_dir)
    enriched = engine.enrich(target, level)
    engine.save_enriched(target, enriched)
    return enriched


def enrich_recon(target: str, level: str = "basic",
                 engagements_dir: str = None) -> Dict[str, Any]:
    """Alias for enrich_target().

    The integration plan refers to this name. Kept as a thin alias rather than a
    rename so existing callers of enrich_target() keep working.
    """
    return enrich_target(target, level=level, engagements_dir=engagements_dir)


def _selftest() -> int:
    """Self-check. Uses a temp engagements dir; never touches the real tree.
    No network egress: DNS resolution is wrapped in HAS_SOCKET, and the
    fixture target is under .test so socket resolution is skipped anyway."""
    import tempfile

    checks: list[tuple[str, bool]] = []

    with tempfile.TemporaryDirectory() as td:
        target_dir = Path(td) / "example.test"
        target_dir.mkdir(parents=True)
        (target_dir / "recon.json").write_text(
            json.dumps({"target": "example.test", "recon": {"hosts": ["a"]}}),
            encoding="utf-8",
        )

        eng = EnrichmentEngine(td)
        out = eng.enrich("example.test", level="full")
        checks.append(("error absent on existing recon", "error" not in out))
        checks.append(("basic adds dns", "dns" in out["recon"]))
        checks.append(("dns target recorded", out["recon"]["dns"]["target"] == "example.test"))
        checks.append(("enhanced adds whois", "whois" in out["recon"]))
        checks.append(("full adds certificates", "certificates" in out["recon"]))
        checks.append(("metadata enrichment stamped", out["metadata"]["enrichment"]["level"] == "full"))
        checks.append(("metadata timestamp ends Z", out["metadata"]["enrichment"]["timestamp"].endswith("Z")))

        # level gating: basic must not add whois/certificates
        out_basic = eng.enrich("example.test", level="basic")
        checks.append(("basic skips whois", "whois" not in out_basic["recon"]))
        checks.append(("basic skips certificates", "certificates" not in out_basic["recon"]))

        # enhanced gating
        out_enh = eng.enrich("example.test", level="enhanced")
        checks.append(("enhanced has whois", "whois" in out_enh["recon"]))
        checks.append(("enhanced skips certificates", "certificates" not in out_enh["recon"]))

        # missing target
        out_missing = eng.enrich("nope.test")
        checks.append(("missing target returns error", "error" in out_missing))

        # invalid level: no enrichment keys
        out_bad = eng.enrich("example.test", level="bogus")
        checks.append(("bogus level no dns", "dns" not in out_bad["recon"]))
        checks.append(("bogus level still stamps metadata", out_bad["metadata"]["enrichment"]["level"] == "bogus"))

        # save_enriched writes file
        p = eng.save_enriched("example.test", out)
        checks.append(("save_enriched writes file", p.exists()))
        checks.append(("save_enriched path name", p.name == "recon_enriched.json"))
        saved = json.loads(p.read_text(encoding="utf-8"))
        checks.append(("saved is valid json", isinstance(saved, dict)))

        # convenience funcs route to the same engine
        d = enrich_recon("example.test", level="basic", engagements_dir=td)
        checks.append(("enrich_recon alias works", "dns" in d["recon"]))

    failed = [name for name, ok in checks if not ok]
    for name, ok in checks:
        print(f"  [{'OK' if ok else 'FAIL'}] {name}")
    if failed:
        print(f"[!] enrichment selftest: {len(failed)}/{len(checks)} failed: {failed}")
        return 1
    print(f"[+] enrichment selftest: {len(checks)}/{len(checks)} checks passed")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(_selftest())

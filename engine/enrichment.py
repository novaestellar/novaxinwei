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


class EnrichmentEngine:
    """Enriches recon data with threat intelligence."""

    def __init__(self, engagements_dir: str = None):
        """
        Initialize enrichment engine.

        Args:
            engagements_dir: Base engagements directory
        """
        self.engagements_dir = Path(engagements_dir) if engagements_dir else Path("engagements")

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

"""
NovaXinWei Recon Schema Definition

Defines the standardized JSON schema for recon data exchange between NovaXinWei and Novahaku.

Schema v1.0:
- version: Schema version
- target: Target domain
- timestamp: ISO 8601 timestamp
- source: Source skill (novaxinwei/novahaku)
- recon: Reconnaissance data
- dorks: Dork results
- metadata: Statistics and tracking
"""

import json
import datetime
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, asdict


# Schema version
SCHEMA_VERSION = "1.0"


@dataclass
class ReconData:
    """Reconnaissance data structure."""
    subdomains: List[str]
    ports: List[int]
    tech_stack: Dict[str, Any]
    waf: Dict[str, Any]
    origin_ip: Optional[str]
    endpoints: List[str]
    dns: Optional[Dict[str, Any]] = None
    certificates: Optional[List[Dict[str, Any]]] = None
    whois: Optional[Dict[str, Any]] = None


@dataclass
class DorkData:
    """Dork search results."""
    shodan: List[Dict[str, Any]]
    github: List[Dict[str, Any]]


@dataclass
class Metadata:
    """Recon metadata and statistics."""
    fetches: int
    cache_hits: int
    channels_used: List[str]
    duration_seconds: float
    enrichment_level: str = "basic"  # basic/enhanced/full


@dataclass
class ReconSchema:
    """Complete recon schema for data exchange."""
    version: str = SCHEMA_VERSION
    target: str = ""
    timestamp: str = ""
    source: str = "novaxinwei"
    recon: Optional[ReconData] = None
    dorks: Optional[DorkData] = None
    metadata: Optional[Metadata] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = asdict(self)
        # Remove None values
        return {k: v for k, v in result.items() if v is not None}

    def to_json(self, indent: int = 2) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ReconSchema':
        """Create from dictionary."""
        schema = cls(
            version=data.get("version", SCHEMA_VERSION),
            target=data.get("target", ""),
            timestamp=data.get("timestamp", ""),
            source=data.get("source", "novaxinwei"),
        )

        if "recon" in data:
            schema.recon = ReconData(**data["recon"])

        if "dorks" in data:
            schema.dorks = DorkData(**data["dorks"])

        if "metadata" in data:
            schema.metadata = Metadata(**data["metadata"])

        return schema

    @classmethod
    def from_json(cls, json_str: str) -> 'ReconSchema':
        """Create from JSON string."""
        data = json.loads(json_str)
        return cls.from_dict(data)

    def validate(self) -> tuple[bool, str]:
        """
        Validate schema structure.

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not self.target:
            return False, "Missing required field: target"

        if not self.timestamp:
            return False, "Missing required field: timestamp"

        if self.recon is None:
            return False, "Missing required field: recon"

        # Validate recon subfields
        if not isinstance(self.recon.subdomains, list):
            return False, "recon.subdomains must be a list"

        if not isinstance(self.recon.ports, list):
            return False, "recon.ports must be a list"

        if not isinstance(self.recon.tech_stack, dict):
            return False, "recon.tech_stack must be a dict"

        if not isinstance(self.recon.endpoints, list):
            return False, "recon.endpoints must be a list"

        return True, "OK"


def create_recon_schema(
    target: str,
    subdomains: List[str] = None,
    ports: List[int] = None,
    tech_stack: Dict[str, Any] = None,
    waf: Dict[str, Any] = None,
    origin_ip: Optional[str] = None,
    endpoints: List[str] = None,
    dorks: Dict[str, Any] = None,
    metadata: Dict[str, Any] = None,
) -> ReconSchema:
    """
    Convenience function to create a ReconSchema.

    Args:
        target: Target domain
        subdomains: List of subdomains
        ports: List of open ports
        tech_stack: Technology stack
        waf: WAF detection results
        origin_ip: Origin IP address
        endpoints: List of discovered endpoints
        dorks: Dork search results
        metadata: Statistics

    Returns:
        ReconSchema instance
    """
    recon = ReconData(
        subdomains=subdomains or [],
        ports=ports or [],
        tech_stack=tech_stack or {},
        waf=waf or {"detected": False, "product": None},
        origin_ip=origin_ip,
        endpoints=endpoints or [],
    )

    dork_data = None
    if dorks:
        dork_data = DorkData(
            shodan=dorks.get("shodan", []),
            github=dorks.get("github", []),
        )

    meta_data = None
    if metadata:
        meta_data = Metadata(**metadata)

    return ReconSchema(
        target=target,
        timestamp=datetime.datetime.utcnow().isoformat() + "Z",
        recon=recon,
        dorks=dork_data,
        metadata=meta_data,
    )

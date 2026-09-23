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
        if not isinstance(data, dict):
            raise TypeError(
                f"recon schema must be a JSON object, got {type(data).__name__}"
            )
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
        # version is the cross-repo contract key: a payload written for a
        # different schema generation must not be accepted silently.
        if self.version != SCHEMA_VERSION:
            return False, (
                f"Unsupported schema version: {self.version!r} "
                f"(this build speaks {SCHEMA_VERSION!r})"
            )

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
        # utcnow() is deprecated; keep the same naive-UTC + "Z" wire format.
        timestamp=(
            datetime.datetime.now(datetime.timezone.utc)
            .replace(tzinfo=None)
            .isoformat()
            + "Z"
        ),
        recon=recon,
        dorks=dork_data,
        metadata=meta_data,
    )


def _selftest() -> int:
    """Self-check. Runs standalone, touches nothing on disk."""
    checks = []
    from dataclasses import fields as _dc_fields

    # --- round trip: the contract's whole purpose ---
    s = create_recon_schema(
        target="example.com",
        subdomains=["a.example.com"],
        ports=[80, 443],
        tech_stack={"web": "nginx"},
        waf={"detected": True, "product": "cloudflare"},
        endpoints=["/api"],
        dorks={"shodan": [{"ip": "1.2.3.4"}], "github": []},
        metadata={"fetches": 3, "cache_hits": 1,
                  "channels_used": ["dns"], "duration_seconds": 1.5},
    )
    ok, msg = s.validate()
    checks.append(("created schema validates", ok))
    checks.append(("validate message is OK", msg == "OK"))

    try:
        back = ReconSchema.from_json(s.to_json())
    except Exception as e:
        checks.append((f"JSON round trip must not raise (got {type(e).__name__})", False))
        back = None
    if back is not None:
        checks.append(("JSON round trip preserves target", back.target == s.target))
        has_recon = back.recon is not None
        checks.append(("round trip keeps recon section", has_recon))
        if has_recon:
            assert back.recon is not None
            checks.append(("JSON round trip preserves subdomains",
                           back.recon.subdomains == ["a.example.com"]))
            checks.append(("JSON round trip preserves ports",
                           back.recon.ports == [80, 443]))
        has_meta = back.metadata is not None
        checks.append(("round trip keeps metadata section", has_meta))
        if has_meta:
            assert back.metadata is not None
            checks.append(("JSON round trip preserves metadata",
                           back.metadata.fetches == 3))
        checks.append(("round trip re-validates", back.validate()[0] is True))
        checks.append(("from_dict agrees with from_json",
                       ReconSchema.from_dict(s.to_dict()).to_json() == s.to_json()))

    # --- to_dict drops None, so absent sections stay absent on the wire ---
    bare = create_recon_schema(target="bare.example")
    d = bare.to_dict()
    checks.append(("to_dict omits None sections",
                   "dorks" not in d and "metadata" not in d))
    checks.append(("to_dict keeps recon", "recon" in d))
    checks.append(("to_dict default waf is present",
                   d["recon"]["waf"] == {"detected": False, "product": None}))
    checks.append(("bare target still validates", bare.validate()[0] is True))

    # --- negative: every required field must actually be enforced ---
    neg = [
        ("missing target", create_recon_schema(target="")),
        ("missing recon", ReconSchema(target="x", timestamp="t", recon=None)),
    ]
    s2 = create_recon_schema(target="x")
    s2.timestamp = ""
    neg.append(("missing timestamp", s2))
    for name, obj in neg:
        valid, _ = obj.validate()
        checks.append((f"rejected: {name}", valid is False))

    # --- negative: recon subfields are type-checked, not just present ---
    for label, mut in (
        ("subdomains as str", lambda r: setattr(r, "subdomains", "nope")),
        ("ports as int", lambda r: setattr(r, "ports", 443)),
        ("tech_stack as list", lambda r: setattr(r, "tech_stack", [])),
        ("endpoints as dict", lambda r: setattr(r, "endpoints", {})),
    ):
        obj = create_recon_schema(target="x")
        mut(obj.recon)
        checks.append((f"rejected: {label}", obj.validate()[0] is False))

    # --- version is the cross-repo contract key: it must be current ---
    checks.append(("version is SCHEMA_VERSION",
                   create_recon_schema(target="x").version == SCHEMA_VERSION))
    checks.append(("validate rejects a foreign schema version",
                   ReconSchema(target="x", timestamp="t", version="9.9",
                               recon=create_recon_schema(target="x").recon
                               ).validate()[0] is False))

    # --- every declared field is constructible from a dict (drift guard) ---
    names = {f.name for f in _dc_fields(ReconData)}
    payload = {"subdomains": [], "ports": [], "tech_stack": {}, "waf": {},
               "origin_ip": None, "endpoints": [], "dns": None,
               "certificates": None, "whois": None}
    checks.append(("ReconData field set matches documented payload",
                   names == set(payload)))
    checks.append(("full ReconData constructs from dict",
                   isinstance(ReconData(**payload), ReconData)))

    # --- robustness: malformed input must raise a clear error, not corrupt ---
    for name, bad in (("not JSON", "{nope"), ("JSON list", "[1,2,3]")):
        try:
            ReconSchema.from_json(bad)
            outcome = "no error"
        except (json.JSONDecodeError, TypeError):
            outcome = "clean"
        except Exception as e:  # an unrelated crash is a defect, not a pass
            outcome = f"unclear:{type(e).__name__}"
        checks.append((f"clear error on {name}", outcome == "clean"))

    failed = [name for name, ok in checks if not ok]
    for name, ok in checks:
        print(f"  [{'OK' if ok else 'FAIL'}] {name}")
    if failed:
        print(f"[!] recon_schema selftest: {len(checks) - len(failed)}/{len(checks)} failed: {failed}")
        return 1
    print(f"[+] recon_schema selftest: {len(checks)}/{len(checks)} checks passed")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(_selftest())

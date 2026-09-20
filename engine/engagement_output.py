"""
NovaXinWei Engagement Output Module

Creates engagement directory structure compatible with Novahaku.
Output: engagements/<target>/recon.json + metadata.json

Usage:
    from engine.engagement_output import EngagementManager
    em = EngagementManager("example.com")
    em.create_dirs()
    em.write_recon(recon_data)
    em.write_metadata(stats)
"""

import json
import os
import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any


class EngagementManager:
    """Manages engagement directory structure for recon output."""

    def __init__(self, target: str, base_dir: Optional[str] = None):
        """
        Initialize engagement manager.

        Args:
            target: Target domain (e.g., "example.com")
            base_dir: Base directory for engagements (default: ./engagements)
        """
        self.target = target
        self.base_dir = Path(base_dir) if base_dir else Path("engagements")
        self.engagement_dir = self.base_dir / target

    def create_dirs(self) -> Path:
        """
        Create engagement directory structure.
        Compatible with Novahaku's recon_pipeline.sh output.

        Returns:
            Path to engagement directory
        """
        dirs = [
            self.engagement_dir,
            self.engagement_dir / "evidence",
            self.engagement_dir / "evidence" / "stage1-seed",
            self.engagement_dir / "evidence" / "stage2-expansion",
            self.engagement_dir / "evidence" / "stage3-enrichment",
            self.engagement_dir / "evidence" / "breach",
            self.engagement_dir / "evidence" / "identity",
            self.engagement_dir / "evidence" / "ports",
            self.engagement_dir / "evidence" / "js",
            self.engagement_dir / "recon",
            self.engagement_dir / "findings",
            self.engagement_dir / "notes",
            self.engagement_dir / "assets",
        ]

        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)

        return self.engagement_dir

    def write_recon(self, recon_data: Dict[str, Any]) -> Path:
        """
        Write recon.json with standardized schema.

        Args:
            recon_data: Recon data dictionary

        Returns:
            Path to recon.json
        """
        self.create_dirs()

        # Add metadata
        output = {
            "version": "1.0",
            "target": self.target,
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
            "source": "novaxinwei",
            "recon": recon_data,
        }

        recon_path = self.engagement_dir / "recon.json"
        with open(recon_path, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

        return recon_path

    def write_metadata(self, stats: Dict[str, Any]) -> Path:
        """
        Write metadata.json with fetch statistics.

        Args:
            stats: Statistics dictionary

        Returns:
            Path to metadata.json
        """
        self.create_dirs()

        metadata = {
            "target": self.target,
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
            "stats": stats,
        }

        meta_path = self.engagement_dir / "metadata.json"
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        return meta_path

    def write_evidence(self, stage: str, filename: str, content: str) -> Path:
        """
        Write evidence file to appropriate stage directory.

        Args:
            stage: Stage name (stage1-seed, stage2-expansion, stage3-enrichment, breach, identity, ports, js)
            filename: Filename to write
            content: File content

        Returns:
            Path to evidence file
        """
        self.create_dirs()

        evidence_dir = self.engagement_dir / "evidence" / stage
        evidence_dir.mkdir(parents=True, exist_ok=True)

        evidence_path = evidence_dir / filename
        with open(evidence_path, "w", encoding="utf-8") as f:
            f.write(content)

        return evidence_path

    def read_recon(self) -> Optional[Dict[str, Any]]:
        """
        Read existing recon.json if it exists.

        Returns:
            Recon data dictionary or None if not found
        """
        recon_path = self.engagement_dir / "recon.json"

        if not recon_path.exists():
            return None

        with open(recon_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def exists(self) -> bool:
        """Check if engagement directory exists."""
        return self.engagement_dir.exists()


def create_engagement(target: str, recon_data: Optional[Dict[str, Any]] = None,
                      stats: Optional[Dict[str, Any]] = None) -> EngagementManager:
    """
    Convenience function to create engagement directory with data.

    Args:
        target: Target domain
        recon_data: Optional recon data
        stats: Optional statistics

    Returns:
        EngagementManager instance
    """
    em = EngagementManager(target)
    em.create_dirs()

    if recon_data:
        em.write_recon(recon_data)

    if stats:
        em.write_metadata(stats)

    return em

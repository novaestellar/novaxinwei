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


def validate_target_name(target: str) -> str:
    """Validate a target as a single directory name and return it trimmed.

    Lives here rather than in engagement_writer because engagement_writer
    imports EngagementManager from this module at load time; importing back
    would be a cycle. engagement_writer re-exports this name, so callers that
    already import from there keep working.

    A target arrives from recon output, so it is untrusted. Rejecting up front
    turns every hostile name into the single documented failure mode,
    ValueError, instead of a raw NotADirectoryError from mkdir halfway through
    building the tree.

    Raises:
        ValueError: empty, whitespace-padded, too long, or containing a path
            separator, "..", a NUL byte, or a Windows-illegal character.
    """
    if not target or not target.strip():
        raise ValueError("target must not be empty")
    if target != target.strip():
        raise ValueError(f"target must not have leading/trailing spaces: {target!r}")
    if len(target) > 255:
        raise ValueError(f"target too long ({len(target)} chars, max 255): {target[:40]!r}...")
    if os.sep in target or (os.altsep and os.altsep in target) or ".." in target:
        raise ValueError(f"target must not contain path separators: {target!r}")
    if os.path.isabs(target):
        raise ValueError(f"target must be a plain directory name: {target!r}")
    if "\x00" in target:
        raise ValueError(f"target must not contain NUL bytes: {target!r}")
    bad = sorted(set('<>:"|?*') & set(target))
    if bad:
        raise ValueError(f"target contains characters illegal on Windows {bad}: {target!r}")
    if any(ord(c) < 32 for c in target):
        raise ValueError(f"target must not contain control characters: {target!r}")
    return target


class EngagementManager:
    """Manages engagement directory structure for recon output."""

    def __init__(self, target: str, base_dir: Optional[str] = None):
        """
        Initialize engagement manager.

        Args:
            target: Target domain (e.g., "example.com"). Must be a plain
                directory name - see validate_target_name().
            base_dir: Base directory for engagements (default: ./engagements)

        Raises:
            ValueError: target is empty, padded, too long, or path-like. Checked
                here, in the constructor, because every method below builds paths
                from self.engagement_dir: validating only in write_engagement
                left `engagement create --target ../escaped.example` able to write
                outside base_dir, and left the other methods raising raw
                NotADirectoryError instead of the documented ValueError.
        """
        validate_target_name(target)
        self.target = target
        # Precedence: explicit base_dir, then NOVAHAKU_ENGAGEMENT_DIR, then
        # <skill root>/engagements. The env var is the shared engagements root that
        # novahaku's engagement.py/engage_runner.py and the web2-recon scripts
        # already honour; ignoring it here meant a pipeline with the variable set
        # wrote recon.json to ./engagements while novahaku read the env dir, so
        # neither side saw the other's files. The fallback was also ./engagements
        # (CWD-relative), so without the env var the two skills landed on
        # different roots whenever either ran from another directory; the skill
        # root anchor makes both resolve the same path from any CWD.
        if base_dir:
            self.base_dir = Path(base_dir)
        elif os.environ.get("NOVAHAKU_ENGAGEMENT_DIR", "").strip():
            self.base_dir = Path(os.environ["NOVAHAKU_ENGAGEMENT_DIR"].strip())
        else:
            self.base_dir = Path(__file__).resolve().parent.parent / "engagements"
        self.engagement_dir = self.base_dir / target

    def _assert_inside_base(self) -> None:
        """Belt and braces: refuse to write when the resolved dir escaped base.

        validate_target_name() already blocks every known escape, but a path
        check on the resolved result is the check that cannot be talked around.
        """
        base = self.base_dir.resolve()
        target = self.engagement_dir.resolve()
        if base != target and base not in target.parents:
            raise ValueError(
                "target resolves outside the engagements directory: %r" % (self.target,)
            )

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

        self._assert_inside_base()
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
        self._assert_inside_base()
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
        self._assert_inside_base()
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
        self._assert_inside_base()
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


def _selftest() -> int:
    """Self-check. Uses a temp base dir; never touches the real engagements/.
    No network egress, no DNS."""
    import tempfile

    checks: list[tuple[str, bool]] = []
    ok_target = "example.test"

    # --- validate_target_name: rejects, never crashes ---
    for bad, label in [("", "empty"), ("   ", "whitespace"), (" a", "leading space"),
                       ("/abs", "leading slash"), ("../esc", "dotdot"), ("a\\b", "backslash"),
                       ("a\x00b", "nul byte"), ("a<b", "angle bracket"), ("a|b", "pipe"),
                       ("a:b", "colon"), ("a\tb", "control char"), ("x" * 300, "too long")]:
        try:
            validate_target_name(bad)
            checks.append((f"reject {label}", False))
        except ValueError:
            checks.append((f"reject {label}", True))
    checks.append(("accept plain host", validate_target_name("example.test") == "example.test"))

    with tempfile.TemporaryDirectory() as td:
        em = EngagementManager(ok_target, base_dir=td)
        checks.append(("engagement_dir under base", str(em.engagement_dir).startswith(td)))
        d = em.create_dirs()
        checks.append(("create_dirs returns dir", d.exists()))
        checks.append(("evidence tree exists", (em.engagement_dir / "evidence" / "breach").exists()))
        checks.append(("recon dir exists", (em.engagement_dir / "recon").exists()))

        # path escape blocked by _assert_inside_base
        em2 = EngagementManager(ok_target, base_dir=td)
        em2.engagement_dir = em2.base_dir.parent  # force escape
        try:
            em2.create_dirs()
            checks.append(("escape blocked", False))
        except ValueError:
            checks.append(("escape blocked", True))

        # write_recon roundtrip
        p = em.write_recon({"hosts": ["a.test"]})
        checks.append(("recon.json written", p.exists()))
        data = json.loads(p.read_text(encoding="utf-8"))
        checks.append(("recon has version", data["version"] == "1.0"))
        checks.append(("recon target matches", data["target"] == ok_target))
        checks.append(("recon source", data["source"] == "novaxinwei"))
        checks.append(("recon timestamp Z", data["timestamp"].endswith("Z")))

        # write_metadata
        mp = em.write_metadata({"fetched": 3})
        meta = json.loads(mp.read_text(encoding="utf-8"))
        checks.append(("metadata stats", meta["stats"] == {"fetched": 3}))

        # write_evidence
        ev = em.write_evidence("breach", "sample.txt", "content")
        checks.append(("evidence written", ev.exists()))
        checks.append(("evidence content", ev.read_text(encoding="utf-8") == "content"))

        # read_recon / exists
        checks.append(("read_recon roundtrip", em.read_recon()["target"] == ok_target))
        checks.append(("exists true", em.exists() is True))

        # env-var root precedence
        import os as _os
        _os.environ["NOVAHAKU_ENGAGEMENT_DIR"] = td
        try:
            em3 = EngagementManager("env-target.test")
            checks.append(("env dir precedence", str(em3.base_dir) == str(Path(td))))
        finally:
            _os.environ.pop("NOVAHAKU_ENGAGEMENT_DIR", None)

        # convenience create_engagement
        cm = create_engagement("conv.test", recon_data={"a": 1}, stats={"s": 1}, )
        # base_dir defaults to skill-root/engagements — use explicit to stay in tmp:
        em4 = EngagementManager("conv.test", base_dir=td)
        em4.create_dirs()
        checks.append(("manager construct ok", em4.exists()))

    failed = [name for name, ok in checks if not ok]
    for name, ok in checks:
        print(f"  [{'OK' if ok else 'FAIL'}] {name}")
    if failed:
        print(f"[!] engagement_output selftest: {len(failed)}/{len(checks)} failed: {failed}")
        return 1
    print(f"[+] engagement_output selftest: {len(checks)}/{len(checks)} checks passed")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(_selftest())

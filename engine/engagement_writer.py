"""
NovaXinWei Engagement Writer

Writes recon output into engagements/<target>/ so Novahaku can consume it.

Thin wrapper over engine/engagement_output.py, which already creates the shared
directory tree and writes recon.json + metadata.json. This module adds the
write_engagement(target, recon_data) entry point named in INTEGRATION_PLAN.md,
plus schema validation before write.

Why a wrapper and not a second implementation: duplicating the directory logic
would create two places to drift, and a caller could get a different layout
depending on which entry point it used.

No cross-skill imports. Stdlib only.

Usage:
    from engine.engagement_writer import write_engagement
    from engine.recon_schema import create_recon_schema
    schema = create_recon_schema("example.com", subdomains=["a.example.com"])
    path = write_engagement("example.com", schema.to_dict())
"""

import json
import os
import sys
from typing import Any, Dict, Optional

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from engagement_output import EngagementManager, validate_target_name  # type: ignore
from engagement_schema import MAX_DEPTH, validate_recon  # type: ignore

# Re-exported for callers that import it from here. One definition, kept in
# engagement_output, because importing it back from there would be a cycle.
__all__ = ["write_engagement", "write_engagement_chained", "json_depth",
           "validate_target_name", "MAX_PAYLOAD_DEPTH"]

# json.dump recurses per nesting level, so a deeply nested payload raises
# RecursionError before it can be written. Far beyond any real recon shape (the
# deepest field, certificates, is ~4 levels) and well under the interpreter
# limit. Sourced from engagement_schema so the validator and the writer cannot
# drift apart: one number, one place. The local check stays as a second line of
# defence for callers that pass validate=False.
MAX_PAYLOAD_DEPTH = MAX_DEPTH


def json_depth(value: Any, _current: int = 0) -> int:
    """Maximum nesting depth of ``value``. Iterative, so it cannot recurse itself.

    Guards the write path against payloads that would blow json.dump's stack.
    """
    stack = [(value, 1)]
    deepest = 0
    while stack:
        node, depth = stack.pop()
        if depth > deepest:
            deepest = depth
        if deepest > MAX_PAYLOAD_DEPTH:
            return deepest
        if isinstance(node, dict):
            for v in node.values():
                stack.append((v, depth + 1))
        elif isinstance(node, (list, tuple)):
            for v in node:
                stack.append((v, depth + 1))
    return deepest


def write_engagement(
    target: str,
    recon_data: Dict[str, Any],
    base_dir: Optional[str] = None,
    validate: bool = True,
    strict: bool = False,
) -> Optional[str]:
    """Write an engagement directory with recon.json and metadata.json.

    Args:
        target: Target domain, used as the engagement directory name.
        recon_data: Recon payload. Should satisfy engine.engagement_schema.
        base_dir: Base engagements directory (default: ./engagements).
        validate: Run schema validation before writing.
        strict: When True, refuse to write an invalid payload. When False
            (default), warn and write anyway so a fetch that succeeded is not
            thrown away over a schema complaint.

    Returns:
        Absolute path to the engagement directory, or None when the write was
        refused by strict validation.

    Raises:
        ValueError: target is empty, padded with spaces, longer than 255, or
            contains a path separator, "..", a NUL byte, or a Windows-illegal
            character (<>:"|?* or a control character).
        TypeError: recon_data is not a dict.
        RecursionError: recon_data nests deeper than MAX_PAYLOAD_DEPTH is
            allowed to (json.dump would blow the stack).
    """
    validate_target_name(target)
    # Checked before validation and before the non-strict path is allowed to
    # continue: validate_recon() reports a non-dict as a *warning*, and the
    # non-strict path would then reach recon_data.get() and raise AttributeError
    # after already printing "writing engagement...". Fail clearly instead.
    if not isinstance(recon_data, dict):
        raise TypeError(f"recon_data must be a dict, got {type(recon_data).__name__}")

    if validate:
        errors = validate_recon(recon_data)
        if errors:
            if strict:
                print(f"[!] Refusing to write engagement for {target}:")
                for e in errors:
                    print(f"    - {e}")
                return None
            print(f"[!] Writing engagement for {target} with schema warnings:")
            for e in errors:
                print(f"    - {e}")

    # Depth is checked separately from validate_recon because that validator only
    # inspects top-level types. A 1500-deep payload passes validation, then dies
    # inside json.dump with RecursionError, which is not a JSONDecodeError and so
    # escaped every handler here - a fetched-but-hostile payload could kill a
    # caller that had already done its real work. Refuse before any directory is
    # created.
    if json_depth(recon_data) > MAX_PAYLOAD_DEPTH:
        print(f"[!] Refusing to write engagement for {target}: "
              f"payload nested deeper than {MAX_PAYLOAD_DEPTH} levels")
        return None

    manager = EngagementManager(target, base_dir=base_dir)
    # create_dirs() builds evidence/, recon/, findings/, notes/ - the shared
    # convention Novahaku's recon_pipeline.sh also uses.
    manager.create_dirs()
    # write_recon() treats its argument as the *contents* of the "recon" key and
    # wraps it in the envelope itself. Passing a full recon payload would nest it
    # one level too deep, so Novahaku's reader would look in recon.subdomains and
    # find nothing. Hand it only the recon block; the rest is rebuilt by
    # write_recon() from the same values.
    manager.write_recon(recon_data.get("recon", {}))

    # metadata.json records that this side produced the recon, and when.
    manager.write_metadata({
        "source": "novaxinwei",
        "artifact": "recon.json",
        "schema_version": recon_data.get("version", "unknown"),
    })

    return str(manager.engagement_dir.resolve())


def engagement_exists(target: str, base_dir: Optional[str] = None) -> bool:
    """True when engagements/<target>/ already exists."""
    return EngagementManager(target, base_dir=base_dir).exists()


def write_engagement_chained(
    target: str,
    recon_data: Dict[str, Any],
    base_dir: Optional[str] = None,
    validate: bool = True,
    strict: bool = False,
) -> Optional[str]:
    """write_engagement() + a chain.json entry recording this contribution.

    Novahaku may have created the engagement first and already tested it. Without
    a chain entry, this side cannot tell whether its recon supersedes Novahaku's
    results. Recording here keeps the start order visible to both sides.

    Returns the engagement path, or None when strict validation refused the write.
    """
    path = write_engagement(
        target, recon_data, base_dir=base_dir, validate=validate, strict=strict
    )
    if path is None:
        return None
    # Imported here, not at module top: chain_state is optional, and a failure to
    # load it must not stop an engagement from being written.
    #
    # Import by bare module name, not "engine.chain_state": this module inserts
    # its own directory onto sys.path (see _HERE), so the surrounding package
    # ("engine") is not importable from here. Asking for engine.chain_state
    # raised ModuleNotFoundError on every production call, which the except
    # below then swallowed into a warning - chain.json silently never recorded
    # the recon. Try the package-qualified form as a fallback for callers that
    # import this as part of the package.
    try:
        try:
            from chain_state import record
        except ImportError:
            from engine.chain_state import record

        record(
            target,
            by="novaxinwei",
            action="recon_written",
            path="recon.json",
            base_dir=base_dir,
        )
    except Exception as exc:  # chain bookkeeping must never lose the recon
        print(f"[!] recon.json written but chain.json not updated: {exc}")
    return path


def read_engagement(target: str, base_dir: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Read recon.json back. None when absent, unreadable, or not an object.

    EngagementManager.read_recon() has no error handling of its own: it raises
    on a corrupt, empty, or binary file, and returns a non-dict for a JSON array.
    This is the public entry point, so the tolerance belongs here rather than in
    the manager, whose behaviour other callers may rely on.
    """
    raw_path = os.path.join(
        str(EngagementManager(target, base_dir=base_dir).engagement_dir), "recon.json"
    )
    if not os.path.exists(raw_path):
        return None
    try:
        with open(raw_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (json.JSONDecodeError, IOError, UnicodeDecodeError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _selftest() -> int:
    """Self-check in a temp dir. Touches nothing real."""
    import shutil
    import tempfile

    base = tempfile.mkdtemp(prefix="novaxinwei-writer-selftest-")
    target = "selftest.example"
    checks = []
    try:
        valid = {
            "version": "1.0",
            "target": target,
            "timestamp": "2026-09-23T00:00:00Z",
            "source": "novaxinwei",
            "recon": {
                "subdomains": ["a.selftest.example"], "ports": [80, 443],
                "tech_stack": {"nginx": "1.18"}, "waf": {"detected": False},
                "origin_ip": "203.0.113.9", "endpoints": ["/api"],
            },
            "metadata": {"fetches": 1},
        }

        path = write_engagement(target, valid, base_dir=base)
        checks.append(("write_engagement returns a path", bool(path)))
        assert path is not None, "write_engagement returned None for a valid payload"
        checks.append(("engagement dir exists", os.path.isdir(path)))

        # Shared convention: all four subdirs, matching Novahaku's pipeline.
        for sub in ("evidence", "recon", "findings", "notes"):
            checks.append((f"{sub}/ created", os.path.isdir(os.path.join(path, sub))))

        recon_file = os.path.join(path, "recon.json")
        meta_file = os.path.join(path, "metadata.json")
        checks.append(("recon.json written", os.path.exists(recon_file)))
        checks.append(("metadata.json written", os.path.exists(meta_file)))

        with open(recon_file, encoding="utf-8") as fh:
            back = json.load(fh)
        # write_recon() owns the envelope: it stamps its own timestamp/source.
        # What must survive is the recon payload, at the right depth.
        checks.append(("envelope keys correct",
                       set(back.keys()) == {"version", "target", "timestamp", "source", "recon"}))
        checks.append(("recon payload preserved", back.get("recon") == valid["recon"]))
        checks.append(("recon NOT nested one level too deep",
                       "recon" not in back.get("recon", {})))
        checks.append(("target preserved", back.get("target") == target))
        checks.append(("source stamped by writer", back.get("source") == "novaxinwei"))
        checks.append(("timestamp stamped by writer", bool(back.get("timestamp"))))
        checks.append(("reader sees recon block",
                       isinstance(read_engagement(target, base_dir=base), dict)))
        # The field Novahaku actually reads must be reachable at the expected path.
        checks.append(("recon.subdomains reachable",
                       (read_engagement(target, base_dir=base) or {}).get("recon", {})
                       .get("subdomains") == ["a.selftest.example"]))
        checks.append(("engagement_exists true", engagement_exists(target, base_dir=base) is True))

        with open(meta_file, encoding="utf-8") as fh:
            meta = json.load(fh)
        checks.append(("metadata names the source", meta.get("stats", {}).get("source") == "novaxinwei"))
        checks.append(("metadata records schema version",
                       meta.get("stats", {}).get("schema_version") == "1.0"))

        # Non-strict lets a partially-populated payload through, with a warning.
        lax = {**valid, "recon": {**valid["recon"], "ports": "80"}}
        checks.append(("non-strict writes invalid payload",
                       write_engagement("lax.example", lax, base_dir=base) is not None))

        # strict refuses, and writes nothing.
        refused = write_engagement("strict.example", lax, base_dir=base, strict=True)
        checks.append(("strict refuses invalid payload", refused is None))
        checks.append(("strict writes no directory",
                       not os.path.isdir(os.path.join(base, "strict.example"))))

        # empty target is a caller error, not a silent no-op.
        try:
            write_engagement("", valid, base_dir=base)
            checks.append(("empty target raises", False))
        except ValueError:
            checks.append(("empty target raises", True))

        # absent engagement reads as None, not an exception.
        checks.append(("absent read returns None",
                       read_engagement("nope.example", base_dir=base) is None))
    finally:
        shutil.rmtree(base, ignore_errors=True)

    failed = [n for n, ok in checks if not ok]
    for n, ok in checks:
        print(f"  [{'OK' if ok else 'FAIL'}] {n}")
    if failed:
        print(f"[!] engagement_writer selftest: {len(failed)}/{len(checks)} failed: {failed}")
        return 1
    print(f"[+] engagement_writer selftest: {len(checks)}/{len(checks)} checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(_selftest())

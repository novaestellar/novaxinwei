"""
NovaXinWei Chain State

Records who started an engagement and when each side last contributed, so the
integration works with either side going first.

The integration is not one-directional. Three orders are valid:

    Path A: recon first   -> NovaXinWei writes recon  -> Novahaku tests
    Path B: test first    -> Novahaku tests           -> NovaXinWei enriches
    Path C: alternating   -> several passes, each side building on the last

Without a shared record, whichever side runs second cannot tell whether its view
of the engagement is current, and would act on a stale picture. chain.json fixes
that: append-only history plus a small current-state block.

No cross-skill imports. Stdlib only.

Usage:
    from engine.chain_state import record, read_chain, is_stale
    record("example.com", by="novaxinwei", action="recon_written", path="recon.json")
    chain = read_chain("example.com")
    if is_stale(chain, mine="novahaku"):
        print("my output predates the other side's contribution")
"""

import datetime
import json
import os
import sys
import time
from typing import Any, Dict, Optional


def _warn(message: str) -> None:
    """Best-effort stderr note. Silent when stderr is closed (batched callers)."""
    try:
        sys.stderr.write("[!] %s\n" % message)
    except Exception:
        pass


_ILLEGAL_WIN_CHARS = set('<>:"|?*')

# A target becomes a directory name. Keep one definition shared with
# engagement_writer so the two writers cannot disagree on what is valid: a colon
# passed chain_state but raised NotADirectoryError in write_engagement.


CHAIN_VERSION = "novalabs.chain.v1"
CHAIN_FILENAME = "chain.json"

# Canonical side names. Matches source values used in recon.json / results.json.
SIDE_NOVAXINWEI = "novaxinwei"
SIDE_NOVAHINAKU = "novahaku"

# Which state key records a side's last contribution.
_STATE_KEY = {
    SIDE_NOVAXINWEI: ("recon_at", "recon_by"),
    SIDE_NOVAHINAKU: ("results_at", "results_by"),
}


def _now() -> str:
    """UTC timestamp with microsecond precision.

    Second precision is not enough: Novahaku and NovaXinWei can both write within
    the same second, and is_stale() decides direction by comparing these strings.
    Equal timestamps would make the comparison silently report "not stale" for
    both sides. Microseconds keep the ordering total.
    """
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


_ILLEGAL_WIN_CHARS = set('<>:"|?*')


def _validate_target(target: str) -> None:
    """Reject target values that cannot safely name one directory.

    Target arrives from recon output (a host name), never a path, so anything
    path-like is a bug or an attack. Without this, os.path.join(root, target)
    happily escapes base_dir: '../x' writes outside engagements/ entirely, and
    an absolute target ignores root altogether. Same rule as
    engagement_writer.write_engagement, so both writers agree on what a valid
    target is.
    """
    if not target or not target.strip():
        raise ValueError("target must not be empty")
    if target != target.strip():
        raise ValueError("target must not have leading/trailing spaces: %r" % (target,))
    if len(target) > 255:
        raise ValueError("target too long (%d chars, max 255): %r..." % (len(target), target[:40]))
    if os.sep in target or (os.altsep and os.altsep in target):
        raise ValueError("target must not contain a path separator: %r" % (target,))
    if os.path.isabs(target) or target in (".", ".."):
        raise ValueError("target must be a plain directory name: %r" % (target,))
    if "\x00" in target:
        raise ValueError("target must not contain NUL bytes: %r" % (target,))
    if any(c in _ILLEGAL_WIN_CHARS or ord(c) < 32 for c in target):
        raise ValueError("target contains a character illegal in a path: %r" % (target,))


def _default_root() -> str:
    """Shared engagements root: NOVAHAKU_ENGAGEMENT_DIR, else ./engagements.

    Same precedence as novahaku's engagement.py / engage_runner.py and this
    repo's engagement_output.py. Previously this used os.getcwd() only, so with
    the env var set the two sides resolved different roots for one target and
    each reported the other's chain.json as missing.
    """
    env = os.environ.get("NOVAHAKU_ENGAGEMENT_DIR", "").strip()
    return os.path.abspath(env) if env else os.path.join(os.getcwd(), "engagements")


def _chain_path(target: str, base_dir: Optional[str] = None) -> str:
    root = os.path.abspath(base_dir) if base_dir else _default_root()
    out = os.path.join(root, target, CHAIN_FILENAME)
    # Belt and braces: even if the guard above is ever loosened, never write
    # outside root.
    if os.path.commonpath([os.path.abspath(out), root]) != os.path.abspath(root):
        raise ValueError("target escapes the engagements directory: %r" % (target,))
    return out


class _ChainLock:
    """Exclusive lock around chain.json read-modify-write.

    Without it, two writers that read the same chain both append to their own
    copy and the loser's entry is overwritten - measured 97% of 150 concurrent
    entries lost. os.replace alone is atomic per write but does not make
    read-then-write atomic. Uses O_EXCL create, which is atomic on both Windows
    and POSIX and needs no new dependency. Stale locks are broken on age so a
    killed process cannot wedge the chain forever.
    """

    _STALE_AFTER = 30.0

    def __init__(self, path: str) -> None:
        self.path = path + ".lock"
        self._held = False

    def __enter__(self) -> "_ChainLock":
        # Each critical section is a few ms of file I/O, but Windows can stall an
        # unlink for hundreds of ms under contention. 6 processes x 25 writes
        # needed more than 15s to serialise, so the deadline is generous: the
        # cost of waiting is latency, the cost of giving up is a lost audit entry.
        deadline = time.time() + 60.0
        while True:
            try:
                fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.close(fd)
                self._held = True
                return self
            except FileExistsError:
                try:
                    if time.time() - os.path.getmtime(self.path) > self._STALE_AFTER:
                        os.remove(self.path)
                        continue
                except OSError:
                    pass
                if time.time() >= deadline:
                    # Could not serialise in time. Proceed without the lock
                    # rather than fail the caller's real work; the write still
                    # cannot corrupt the file, it can only lose an entry.
                    return self
                time.sleep(0.005)
            except OSError:
                # Windows reports a delete-pending or briefly-locked lock file as
                # PermissionError from O_EXCL, not FileExistsError. Treat it like
                # contention and retry, otherwise one unlucky writer silently
                # proceeds unlocked and its entry can be overwritten.
                if time.time() >= deadline:
                    return self
                time.sleep(0.005)

    def __exit__(self, *exc: Any) -> bool:
        if self._held:
            try:
                os.remove(self.path)
            except OSError:
                pass
        return False


def read_chain(target: str, base_dir: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Read chain.json. None when absent or unreadable.

    Absence is not an error: an engagement created before chain.json existed has
    no chain, and callers treat that as "start order unknown" rather than failing.
    """
    path = _chain_path(target, base_dir)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (json.JSONDecodeError, IOError, UnicodeDecodeError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    return data


def record(
    target: str,
    by: str,
    action: str,
    path: Optional[str] = None,
    base_dir: Optional[str] = None,
    phase: Optional[str] = None,
) -> Dict[str, Any]:
    """Append one contribution to chain.json and return the updated chain.

    Creates the file on first call, setting started_by to the first writer. Never
    rewrites or removes an existing history entry - the log is the audit trail.

    Args:
        target: Target domain.
        by: Side making the contribution (novaxinwei / novahaku).
        action: Short verb phrase, e.g. "recon_written", "results_written".
        path: Artifact filename the action produced, for traceability.
        base_dir: Base engagements directory.
        phase: Optional engagement phase to mirror into state.

    Returns:
        The updated chain dictionary.

    Raises:
        ValueError: target or by is empty.
    """
    if not target or not target.strip():
        raise ValueError("target must not be empty")
    if not by or not by.strip():
        raise ValueError("by must not be empty")
    _validate_target(target)

    now = _now()
    out = _chain_path(target, base_dir)
    os.makedirs(os.path.dirname(out), exist_ok=True)

    # Read and write under one lock. Reading before acquiring it would let two
    # writers append to the same snapshot and lose the slower one's entry.
    with _ChainLock(out):
        chain = read_chain(target, base_dir)

        if chain is None:
            chain = {
                "version": CHAIN_VERSION,
                "target": target,
                "created": now,
                "updated": now,
                "started_by": by,
                "state": {},
                "history": [],
            }

        chain["updated"] = now
        entry: Dict[str, Any] = {"at": now, "by": by, "action": action}
        if path:
            entry["path"] = path
        history = chain.get("history")
        if not isinstance(history, list):
            history = chain["history"] = []
        history.append(entry)

        # Track where each side last contributed, so either side can check staleness.
        state = chain.get("state")
        if not isinstance(state, dict):
            state = chain["state"] = {}
        keys = _STATE_KEY.get(by)
        if keys:
            state[keys[0]] = now
            state[keys[1]] = by
        if phase:
            state["phase"] = phase

        _write_chain(out, chain)
    return chain


def _write_chain(out: str, chain: Dict[str, Any]) -> None:
    """Persist chain.json atomically, retrying around transient Windows locks.

    Best-effort by contract: the caller's real work (a successful fetch or recon
    write) must never die because the audit trail could not be updated. On
    Windows os.replace raises PermissionError [WinError 32] whenever another
    process has the destination open, so retry briefly and then give up with a
    warning instead of raising.
    """
    tmp = out + ".tmp"
    payload = json.dumps(chain, indent=2, ensure_ascii=False)
    for attempt in range(5):
        try:
            with open(tmp, "w", encoding="utf-8") as fh:
                fh.write(payload)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, out)
            return
        except OSError as exc:
            if attempt == 4:
                try:
                    os.remove(tmp)
                except OSError:
                    pass
                _warn("chain.json not updated for %r: %s" % (chain.get("target"), exc))
                return
            time.sleep(0.02 * (attempt + 1))


def is_stale(chain: Optional[Dict[str, Any]], mine: str) -> bool:
    """True when ``mine`` last contributed before the other side did.

    A stale side would be working from an out-of-date picture of the engagement.
    Returns False when the chain is absent or incomplete - an unknown start order
    is not proof of staleness, and a hard failure there would break old
    engagements for no benefit.
    """
    if not isinstance(chain, dict):
        return False
    state = chain.get("state")
    if not isinstance(state, dict):
        return False

    mine_keys = _STATE_KEY.get(mine)
    other = SIDE_NOVAHINAKU if mine == SIDE_NOVAXINWEI else SIDE_NOVAXINWEI
    other_keys = _STATE_KEY.get(other)
    if not mine_keys or not other_keys:
        return False

    my_at = state.get(mine_keys[0])
    their_at = state.get(other_keys[0])
    if not my_at:
        # Never contributed: nothing of mine can be stale.
        return False
    if not their_at:
        # They never contributed: they cannot have superseded me.
        return False
    return str(my_at) < str(their_at)


def started_by(target: str, base_dir: Optional[str] = None) -> Optional[str]:
    """Which side created the engagement. None when unknown (no chain.json)."""
    chain = read_chain(target, base_dir)
    if not isinstance(chain, dict):
        return None
    value = chain.get("started_by")
    return value if isinstance(value, str) else None


def _selftest() -> int:
    """Self-check in a temp dir. Touches nothing real."""
    import shutil
    import tempfile

    base = tempfile.mkdtemp(prefix="novaxinwei-chain-selftest-")
    target = "chain.example"
    checks = []
    try:
        checks.append(("absent chain returns None", read_chain(target, base) is None))
        checks.append(("absent started_by returns None", started_by(target, base) is None))
        checks.append(("absent chain is not stale", is_stale(None, SIDE_NOVAXINWEI) is False))

        # First writer sets started_by.
        c1 = record(target, by=SIDE_NOVAHINAKU, action="engagement_created",
                    path="state.json", base_dir=base)
        checks.append(("started_by records first writer", c1.get("started_by") == SIDE_NOVAHINAKU))
        checks.append(("version stamped", c1.get("version") == CHAIN_VERSION))
        checks.append(("history has one entry", len(c1.get("history", [])) == 1))
        checks.append(("state.results_at set", bool(c1["state"].get("results_at"))))
        checks.append(("state.results_by set", c1["state"].get("results_by") == SIDE_NOVAHINAKU))
        checks.append(("on disk", os.path.exists(os.path.join(base, target, CHAIN_FILENAME))))

        # Path B: Novahaku started. NovaXinWei following is NOT stale.
        c2 = record(target, by=SIDE_NOVAXINWEI, action="recon_written",
                    path="recon.json", base_dir=base)
        checks.append(("history appends, never replaces", len(c2["history"]) == 2))
        checks.append(("started_by unchanged", c2.get("started_by") == SIDE_NOVAHINAKU))
        checks.append(("recon_at set", bool(c2["state"].get("recon_at"))))

        # Now Novahaku is behind: its last write predates NovaXinWei's.
        checks.append(("novahaku is stale after novaxinwei wrote",
                       is_stale(c2, SIDE_NOVAHINAKU) is True))
        checks.append(("novaxinwei is not stale", is_stale(c2, SIDE_NOVAXINWEI) is False))

        # Novahaku refreshes -> no longer stale.
        c3 = record(target, by=SIDE_NOVAHINAKU, action="results_written",
                    path="results.json", base_dir=base)
        checks.append(("novahaku fresh after its own write",
                       is_stale(c3, SIDE_NOVAHINAKU) is False))
        checks.append(("novaxinwei now stale",
                       is_stale(c3, SIDE_NOVAXINWEI) is True))

        # Ordering is preserved.
        actions = [h["action"] for h in c3["history"]]
        checks.append(("history order preserved",
                       actions == ["engagement_created", "recon_written", "results_written"]))
        checks.append(("paths recorded", c3["history"][1].get("path") == "recon.json"))

        # Phase mirroring.
        c4 = record(target, by=SIDE_NOVAHINAKU, action="phase", phase="report", base_dir=base)
        checks.append(("phase mirrored", c4["state"].get("phase") == "report"))

        # Corrupt chain reads as None, does not raise.
        cp = os.path.join(base, target, CHAIN_FILENAME)
        with open(cp, "w", encoding="utf-8") as fh:
            fh.write("{broken")
        checks.append(("corrupt chain returns None", read_chain(target, base) is None))
        checks.append(("corrupt chain not stale", is_stale(read_chain(target, base), SIDE_NOVAXINWEI) is False))
        checks.append(("recovers after corruption",
                       record(target, by=SIDE_NOVAXINWEI, action="recovered",
                              base_dir=base).get("started_by") == SIDE_NOVAXINWEI))

        # Non-dict chain is tolerated.
        with open(cp, "w", encoding="utf-8") as fh:
            fh.write("[1,2,3]")
        checks.append(("non-dict chain returns None", read_chain(target, base) is None))

        # Argument validation.
        for label, kwargs in [
            ("empty target", {"target": "", "by": SIDE_NOVAHINAKU, "action": "x"}),
            ("empty by", {"target": target, "by": "", "action": "x"}),
        ]:
            try:
                record(base_dir=base, **kwargs)
                checks.append((f"{label} raises", False))
            except ValueError:
                checks.append((f"{label} raises", True))

        # No temp file left behind by the atomic write.
        leftovers = [f for f in os.listdir(os.path.join(base, target)) if f.endswith(".tmp")]
        checks.append(("no .tmp leftover", not leftovers))
    finally:
        shutil.rmtree(base, ignore_errors=True)

    failed = [n for n, ok in checks if not ok]
    for n, ok in checks:
        print(f"  [{'OK' if ok else 'FAIL'}] {n}")
    if failed:
        print(f"[!] chain_state selftest: {len(failed)}/{len(checks)} failed: {failed}")
        return 1
    print(f"[+] chain_state selftest: {len(checks)}/{len(checks)} checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(_selftest())

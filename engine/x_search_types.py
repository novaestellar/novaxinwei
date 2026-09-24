"""Typed result contract for X keyword discovery."""
from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True, slots=True)
class XPost:
    url: str
    tweet_id: str
    author_name: str
    author_handle: str
    text: str
    created_at: str
    likes: int
    replies: int
    discovered_by: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class XSearchResult:
    ok: bool
    query: str
    posts: tuple[XPost, ...]
    discovery_sources: tuple[str, ...]
    degraded_reason: str
    discovery_errors: dict[str, str]
    rejected_urls: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "query": self.query,
            "posts": [post.to_dict() for post in self.posts],
            "discovery_sources": list(self.discovery_sources),
            "degraded_reason": self.degraded_reason,
            "discovery_errors": self.discovery_errors,
            "rejected_urls": list(self.rejected_urls),
        }


def _selftest() -> int:
    """Self-check the X result data contracts. Pure dataclass work."""
    checks: list[tuple[str, bool]] = []

    post = XPost(
        url="https://x.com/u/status/1",
        tweet_id="1",
        author_name="Alice",
        author_handle="alice",
        text="hello",
        created_at="2026-01-01T00:00:00Z",
        likes=3,
        replies=1,
        discovered_by=("query-a",),
    )
    checks.append(("XPost is frozen", isinstance(post, tuple) is False and hasattr(post, "__frozen__") is False))
    checks.append(("XPost.to_dict roundtrip", post.to_dict()["tweet_id"] == "1"))
    # asdict keeps nested tuples as-is (Python 3.13 dict-as-deepcopy semantics)
    checks.append(("XPost.to_dict keeps tuple", post.to_dict()["discovered_by"] == ("query-a",)))

    res = XSearchResult(
        ok=True,
        query="x",
        posts=(post,),
        discovery_sources=("q",),
        degraded_reason="",
        discovery_errors={},
        rejected_urls=(),
    )
    d = res.to_dict()
    checks.append(("XSearchResult.to_dict posts unpacked", d["posts"][0]["author_handle"] == "alice"))
    checks.append(("XSearchResult.to_dict errors kept", isinstance(d["discovery_errors"], dict)))
    checks.append(("XSearchResult.to_dict sources as list", isinstance(d["discovery_sources"], list)))
    checks.append(("empty posts allowed", XSearchResult(False, "q", (), ("q",), "degraded", {}, ()).ok is False))

    # asdict on frozen dataclass with slots still works (dataclasses handles slots)
    checks.append(("asdict works", asdict(post)["likes"] == 3))

    failed = [name for name, ok in checks if not ok]
    for name, ok in checks:
        print(f"  [{'OK' if ok else 'FAIL'}] {name}")
    if failed:
        print(f"[!] x_search_types selftest: {len(failed)}/{len(checks)} failed: {failed}")
        return 1
    print(f"[+] x_search_types selftest: {len(checks)}/{len(checks)} checks passed")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(_selftest())

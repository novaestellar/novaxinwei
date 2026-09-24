"""Selftest for engine/__init__.py, the package's public re-export surface.

engine/__init__.py re-exports 14 names from 6 submodules and lists them in
__all__. Nothing tested it, so a renamed symbol or a dropped import would break
`from engine import fetch` for every consumer while each submodule's own
selftest stayed green — the submodules are tested directly, never through the
package facade.

What this checks is the facade contract, not the submodules' behaviour (they
have their own harnesses): every name in __all__ resolves, __all__ and the
module's actual public attributes agree, and each name is the same object the
declaring submodule exports — so `engine.fetch is engine.fetch_chain.fetch`,
not a stale copy.

Run: python -m engine.__init__ --selftest
"""
from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if os.path.dirname(_HERE) not in sys.path:
    sys.path.insert(0, os.path.dirname(_HERE))


def _selftest() -> int:
    checks: list[tuple[str, bool]] = []

    import engine as pkg

    exported = list(getattr(pkg, "__all__", []))
    checks.append(("__all__ is non-empty", len(exported) > 0))
    checks.append(("__all__ has no duplicates", len(exported) == len(set(exported))))

    # Every advertised name must actually exist — this is the check that catches
    # a symbol renamed in its submodule without updating the facade.
    missing = [n for n in exported if not hasattr(pkg, n)]
    checks.append((f"every __all__ name resolves ({len(exported)} names)", missing == []))

    # A public attribute that is not in __all__ means `from engine import *`
    # silently diverges from the documented surface.
    public = {n for n in vars(pkg) if not n.startswith("_")}
    # Submodules appear as attributes once imported; they are not exports. Under
    # `python -m engine.X` the interpreter imports this package with __main__ set,
    # so engine.__main__ shows up as an attribute here but not when imported
    # normally — exclude any submodule so the check means the same thing in both.
    submodules = {n for n in public
                  if getattr(getattr(pkg, n, None), "__name__", "").startswith("engine.")}
    undeclared = public - set(exported) - submodules
    checks.append((f"no undeclared public names (found: {sorted(undeclared)})", not undeclared))

    # Identity, not equality: catches a facade that re-created a value instead
    # of forwarding the canonical object.
    from engine import validators, waf_detector, url_transforms, fetch_chain, content_safety

    ident = [
        ("Verdict", validators.Verdict),
        ("ValidationResult", validators.ValidationResult),
        ("validate", validators.validate),
        ("CHALLENGE_MARKERS", validators.CHALLENGE_MARKERS),
        ("detect", waf_detector.detect),
        ("TRANSFORMS", url_transforms.TRANSFORMS),
        ("apply_transform", url_transforms.apply_transform),
        ("fetch", fetch_chain.fetch),
        ("FetchResult", fetch_chain.FetchResult),
        ("Attempt", fetch_chain.Attempt),
        ("BEGIN_UNTRUSTED_WEB_CONTENT", content_safety.BEGIN_UNTRUSTED_WEB_CONTENT),
        ("CONTENT_TRUST_UNTRUSTED_PUBLIC_WEB", content_safety.CONTENT_TRUST_UNTRUSTED_PUBLIC_WEB),
        ("END_UNTRUSTED_WEB_CONTENT", content_safety.END_UNTRUSTED_WEB_CONTENT),
        ("ContentSafetyReport", content_safety.ContentSafetyReport),
        ("analyze_untrusted_content", content_safety.analyze_untrusted_content),
        ("wrap_untrusted_content", content_safety.wrap_untrusted_content),
    ]
    for name, canonical in ident:
        checks.append((f"{name} is the submodule's object", getattr(pkg, name, None) is canonical))

    # The untrusted-content fence must be a real fence, not an empty string that
    # would make wrap_untrusted_content a no-op passthrough.
    checks.append(("untrusted-content markers are non-empty",
                   bool(pkg.BEGIN_UNTRUSTED_WEB_CONTENT) and bool(pkg.END_UNTRUSTED_WEB_CONTENT)))
    checks.append(("wrap_untrusted_content actually wraps",
                   pkg.BEGIN_UNTRUSTED_WEB_CONTENT in pkg.wrap_untrusted_content("PROBE")))

    # __version__ lives on the root novaxinwei package, not on engine. Assert the
    # version is reachable one level up and is a sane dotted string, rather than
    # asserting an attribute engine does not define.
    root_ver = None
    try:
        import novaxinwei as root  # layout B
        root_ver = getattr(root, "__version__", None)
    except ImportError:
        try:
            root = sys.modules.get(os.path.basename(os.path.dirname(_HERE)))
            root_ver = getattr(root, "__version__", None) if root else None
        except Exception:
            root_ver = None
    if root_ver is None:
        # Layout A (repo): the root package is the parent dir, importable as
        # whatever it is named on disk; read it as a file to stay layout-agnostic.
        root_init = os.path.join(os.path.dirname(_HERE), "__init__.py")
        if os.path.isfile(root_init):
            with open(root_init, encoding="utf-8") as fh:
                for line in fh:
                    if line.startswith("__version__"):
                        root_ver = line.split("=", 1)[1].strip().strip('"\'')
                        break
    checks.append(("root package __version__ reachable", bool(root_ver)))
    checks.append(("__version__ looks like a version",
                   bool(root_ver) and all(part.isdigit() for part in str(root_ver).split("."))))

    # The docstring states the No-Site-Name Rule; if the facade ever grows
    # site-specific logic this flag makes the reviewer look.
    checks.append(("docstring visible", pkg.__doc__ is not None))

    failed = sum(1 for _n, ok in checks if not ok)
    for name, ok in checks:
        print(f"  [{'OK' if ok else 'FAIL'}] {name}")
    total = len(checks)
    print(f"[{'+' if not failed else '-'}] engine/__init__: {total - failed}/{total} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(_selftest())

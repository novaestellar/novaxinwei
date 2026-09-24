"""Credential and HTTP boundaries for X keyword discovery."""
from __future__ import annotations

import os
import shutil
import subprocess
from typing import Any


def resolve_xai_credential() -> str | None:
    api_key = os.environ.get("XAI_API_KEY", "").strip()
    if api_key:
        return api_key
    omo = shutil.which("omo")
    if not omo:
        return None
    try:
        process = subprocess.run(
            [omo, "auth", "print-bearer-token", "--provider", "xai"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    token = process.stdout.strip()
    return token if process.returncode == 0 and token else None


def http_get(url: str, timeout: int) -> Any:
    from curl_cffi import requests

    return requests.get(url, impersonate="safari", timeout=timeout, allow_redirects=True)


def http_post_json(url: str, payload: dict[str, object], credential: str, timeout: int) -> Any:
    from curl_cffi import requests

    return requests.post(
        url,
        impersonate="safari",
        timeout=timeout,
        headers={"Authorization": f"Bearer {credential}", "Content-Type": "application/json"},
        json=payload,
    )


def _selftest() -> int:
    """Self-check credential resolution. No network, no real subprocess."""
    import os

    checks: list[tuple[str, bool]] = []

    # env var path
    os.environ["XAI_API_KEY"] = "  test-key-123  "
    checks.append(("env key trimmed", resolve_xai_credential() == "test-key-123"))
    os.environ.pop("XAI_API_KEY", None)

    # no env, no omo on PATH in this env
    # (shutil.which returns None here unless the lab has omo installed;
    #  either way resolve must return None WITHOUT raising)
    from unittest.mock import patch

    with patch("shutil.which", return_value=None):
        checks.append(("no omo -> None", resolve_xai_credential() is None))

    # subprocess failure path: omo exists but returns non-zero
    with patch("shutil.which", return_value="/fake/omo"):
        with patch("subprocess.run") as fake_run:
            proc = type("P", (), {"returncode": 1, "stdout": "  "})()
            fake_run.return_value = proc
            checks.append(("non-zero omo -> None", resolve_xai_credential() is None))

    # subprocess success path
    with patch("shutil.which", return_value="/fake/omo"):
        with patch("subprocess.run") as fake_run:
            proc = type("P", (), {"returncode": 0, "stdout": "  token-abc  \n"})()
            fake_run.return_value = proc
            checks.append(("zero omo -> token", resolve_xai_credential() == "token-abc"))

    failed = [name for name, ok in checks if not ok]
    for name, ok in checks:
        print(f"  [{'OK' if ok else 'FAIL'}] {name}")
    if failed:
        print(f"[!] x_search_io selftest: {len(failed)}/{len(checks)} failed: {failed}")
        return 1
    print(f"[+] x_search_io selftest: {len(checks)}/{len(checks)} checks passed")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(_selftest())

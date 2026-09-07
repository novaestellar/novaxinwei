"""NovaXinWei channel utilities — extracted from NovaXinWei.

Provides minimal URL matching, path, text, and process helpers needed by channels.
"""

from __future__ import annotations

import ipaddress
import os
import re
import shutil
import socket
import subprocess
from pathlib import Path
from typing import Mapping, Optional
from urllib.parse import urlsplit


# --- URL helpers (from novaxinwei/utils/url.py) ---

_BLOCKED_PUBLIC_FETCH_HOSTS = {
    "home.arpa", "instance-data", "internal", "ip6-localhost",
    "ip6-loopback", "lan", "local", "localdomain", "localhost",
    "metadata.google.internal",
}
_BLOCKED_PUBLIC_FETCH_SUFFIXES = (
    ".home.arpa", ".internal", ".lan", ".local", ".localdomain", ".localhost",
)


def _literal_ip_address(host: str):
    try:
        return ipaddress.ip_address(host)
    except ValueError:
        pass
    try:
        packed = socket.inet_aton(host)
    except OSError:
        return None
    return ipaddress.IPv4Address(packed)


def normalize_public_http_url(url: str) -> str:
    candidate = str(url or "").strip()
    if (
        not candidate
        or "\\" in candidate
        or any(c.isspace() or ord(c) < 0x20 or ord(c) == 0x7F for c in candidate)
    ):
        raise ValueError("only public HTTP(S) URLs are allowed")
    if "://" not in candidate:
        candidate = f"https://{candidate}"
    try:
        parsed = urlsplit(candidate)
        host = (parsed.hostname or "").lower().rstrip(".")
        _ = parsed.port
    except (TypeError, ValueError):
        raise ValueError("only public HTTP(S) URLs are allowed") from None
    literal_address = _literal_ip_address(host)
    if (
        parsed.scheme.lower() not in {"http", "https"}
        or not host
        or parsed.username is not None
        or parsed.password is not None
        or "%" in host
        or host in _BLOCKED_PUBLIC_FETCH_HOSTS
        or host.endswith(_BLOCKED_PUBLIC_FETCH_SUFFIXES)
        or ("." not in host and literal_address is None)
        or (literal_address is not None and not literal_address.is_global)
    ):
        raise ValueError("only public HTTP(S) URLs are allowed")
    return parsed.geturl()


def host_matches(url: str, *domains: str) -> bool:
    try:
        parsed = urlsplit(url)
        host = (parsed.hostname or "").lower().rstrip(".")
        _ = parsed.port
    except (TypeError, ValueError):
        return False
    if parsed.scheme.lower() not in {"http", "https"}:
        return False
    if not host or parsed.username is not None or parsed.password is not None:
        return False
    for domain in domains:
        allowed = domain.lower().lstrip(".").rstrip(".")
        if host == allowed or host.endswith("." + allowed):
            return True
    return False


def domain_matches(host: str, *domains: str) -> bool:
    normalized = str(host or "").lower().lstrip(".").rstrip(".")
    if not normalized:
        return False
    for domain in domains:
        allowed = domain.lower().lstrip(".").rstrip(".")
        if normalized == allowed or normalized.endswith("." + allowed):
            return True
    return False


# --- Text helpers (from novaxinwei/utils/text.py) ---

_URL_CREDENTIALS_RE = re.compile(r"([A-Za-z][A-Za-z0-9+.\-]{0,19}://)[^\s@]+@")
_BARE_USERINFO_RE = re.compile(r"(?<![A-Za-z0-9._%+\-])[^:/\s@]+:[^\s@]+@(?=[A-Za-z0-9.\-\[])")
_URL_QUERY_SECRET_RE = re.compile(
    r"([?&#](?:access[_-]?token|auth[_-]?token|token|bearer|api[_-]?key|key|password|passwd|secret|signature|sig|session(?:id)?|cookie|credential)=)[^&#\s]*",
    re.IGNORECASE,
)


def scrub_url_credentials(text: object) -> str:
    scrubbed = _URL_CREDENTIALS_RE.sub(r"\1***@", str(text))
    scrubbed = _BARE_USERINFO_RE.sub("***@", scrubbed)
    return _URL_QUERY_SECRET_RE.sub(r"\1***", scrubbed)


# --- Process helpers (from novaxinwei/utils/process.py) ---

UTF8_ENV = {"PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}


def utf8_subprocess_env(base: Mapping[str, str] | None = None) -> dict[str, str]:
    env = dict(base or os.environ)
    env.update(UTF8_ENV)
    return env


# --- Path helpers (from novaxinwei/utils/paths.py) ---

def home_dir() -> Path:
    explicit_home = os.environ.get("HOME")
    if explicit_home:
        return Path(os.path.abspath(explicit_home))
    expanded = os.path.expanduser("~")
    if expanded and expanded != "~":
        return Path(expanded)
    return Path(".")


def config_dir() -> Path:
    return home_dir() / ".config" / "novaxinwei"


# --- Probe helper (from novaxinwei/probe.py) ---

def probe_command(command: str, args: list[str] | None = None, timeout: int = 5) -> dict:
    """Lightweight upstream command probing."""
    exe = shutil.which(command)
    if not exe:
        return {"status": "missing", "output": f"{command} not found on PATH"}
    try:
        result = subprocess.run(
            [exe] + (args or ["--version"]),
            capture_output=True, text=True, timeout=timeout,
            env=utf8_subprocess_env(),
        )
        if result.returncode in (126, 127):
            return {"status": "broken", "output": f"{command} exists but not executable"}
        if result.returncode != 0 and result.returncode != 1:
            return {"status": "error", "output": result.stderr.strip()[:200]}
        return {"status": "ok", "output": result.stdout.strip()[:200]}
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "output": f"{command} timed out after {timeout}s"}
    except Exception as e:
        return {"status": "error", "output": str(e)[:200]}

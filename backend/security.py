"""
Local-network security helpers.

Design:
- localhost remains frictionless for development on the Mac;
- LAN clients, including a phone, must send X-ObsidianAI-Token;
- the generated token is stored only in the local project data directory.
"""

import hashlib
import ipaddress
import secrets
from pathlib import Path
from typing import Optional


DATA_DIR = Path(__file__).parent.parent / "data"
TOKEN_PATH = DATA_DIR / "auth-token.txt"


def ensure_auth_token() -> str:
    DATA_DIR.mkdir(exist_ok=True)
    if TOKEN_PATH.exists():
        token = TOKEN_PATH.read_text(encoding="utf-8").strip()
        if token:
            return token
    token = secrets.token_urlsafe(32)
    TOKEN_PATH.write_text(token + "\n", encoding="utf-8")
    TOKEN_PATH.chmod(0o600)
    return token


def read_auth_token() -> str:
    return ensure_auth_token()


def token_fingerprint(token: Optional[str] = None) -> str:
    raw = token or read_auth_token()
    return hashlib.sha256(raw.encode()).hexdigest()[:12]


def is_loopback_host(host: Optional[str]) -> bool:
    if not host:
        return False
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return host in {"localhost", "::1"}


def is_valid_token(raw: Optional[str]) -> bool:
    if not raw:
        return False
    expected = read_auth_token()
    return secrets.compare_digest(raw.strip(), expected)

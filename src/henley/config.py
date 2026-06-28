"""Configuration and credential loading for Henley.

Credentials live in a ``.keys`` file (git-ignored) at the project root. The
file is the one issued by JLCPCB and looks like::

    JLCAPI:
        AppID:     <your-app-id>
        Accesskey: <your-access-key>
        SecretKey: <your-secret-key>

    Tokenization Key RSA
        Public:
    <base64-rsa-public-key>
        Private
    <base64-rsa-private-key>

The RSA tokenization key is only used for order placement (encrypting
sensitive fields such as shipping addresses); read-only parts queries do not
need it, so it is parsed best-effort and may be absent.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

# JLCPCB global/overseas OpenAPI *API* host. Note: api.jlcpcb.com is the
# developer **portal** (docs/console); live API routes are served from
# open.jlcpcb.com (verified: valid signature -> 403 perms, bad signature -> 401).
# The China host baked into the Java SDK default is https://openapi.jlc.com.
DEFAULT_ENDPOINT = "https://open.jlcpcb.com"


def _project_root() -> Path:
    """Walk up from the cwd looking for a ``.keys`` file, else use cwd."""
    here = Path.cwd()
    for candidate in (here, *here.parents):
        if (candidate / ".keys").exists():
            return candidate
    return here


@dataclass(frozen=True)
class Credentials:
    app_id: str
    access_key: str
    secret_key: str
    rsa_public_b64: str | None = None
    rsa_private_b64: str | None = None


@dataclass(frozen=True)
class Settings:
    credentials: Credentials
    endpoint: str = DEFAULT_ENDPOINT


def _parse_keys(text: str) -> Credentials:
    """Parse the JLCPCB ``.keys`` file.

    The format is YAML-ish but not strictly valid YAML (the RSA section has
    bare labels and unindented base64 blocks), so we parse it line by line.
    """
    app_id = access_key = secret_key = None
    rsa_public = rsa_private = None

    # Simple ``Label: value`` pairs (AppID / Accesskey / SecretKey).
    for key, attr in (("AppID", "app_id"), ("Accesskey", "access_key"), ("SecretKey", "secret_key")):
        m = re.search(rf"^\s*{key}\s*:\s*(\S+)\s*$", text, re.IGNORECASE | re.MULTILINE)
        if m:
            value = m.group(1)
            if attr == "app_id":
                app_id = value
            elif attr == "access_key":
                access_key = value
            else:
                secret_key = value

    # RSA blocks: a "Public"/"Private" label followed by a long base64 line.
    lines = text.splitlines()
    pending = None  # which key the next base64 line fills
    for line in lines:
        stripped = line.strip()
        low = stripped.lower().rstrip(":")
        if low == "public":
            pending = "public"
            continue
        if low == "private":
            pending = "private"
            continue
        if pending and re.fullmatch(r"[A-Za-z0-9+/=]{40,}", stripped):
            if pending == "public":
                rsa_public = stripped
            else:
                rsa_private = stripped
            pending = None

    missing = [n for n, v in (("AppID", app_id), ("Accesskey", access_key), ("SecretKey", secret_key)) if not v]
    if missing:
        raise ValueError(f".keys is missing required field(s): {', '.join(missing)}")

    return Credentials(
        app_id=app_id,
        access_key=access_key,
        secret_key=secret_key,
        rsa_public_b64=rsa_public,
        rsa_private_b64=rsa_private,
    )


def load_credentials(path: str | os.PathLike | None = None) -> Credentials:
    """Load credentials from a ``.keys`` file.

    Path resolution order: explicit ``path`` arg, then ``HENLEY_KEYS`` env var,
    then a ``.keys`` file discovered by walking up from the cwd.
    """
    if path is None:
        path = os.environ.get("HENLEY_KEYS")
    keys_path = Path(path) if path else _project_root() / ".keys"
    if not keys_path.exists():
        raise FileNotFoundError(
            f"No .keys file found at {keys_path}. Set HENLEY_KEYS or run from the project root."
        )
    return _parse_keys(keys_path.read_text())


def _read_endpoint() -> str:
    """Endpoint override order: HENLEY_ENDPOINT env, else the default API host.

    The project ``notes`` file holds the developer-portal URL, not the API host,
    so it is intentionally not used as the endpoint source.
    """
    env = os.environ.get("HENLEY_ENDPOINT")
    if env:
        return env.rstrip("/")
    return DEFAULT_ENDPOINT


def load_settings(keys_path: str | os.PathLike | None = None) -> Settings:
    return Settings(credentials=load_credentials(keys_path), endpoint=_read_endpoint())

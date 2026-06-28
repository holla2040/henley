"""HTTP client for the JLCPCB OpenAPI component (parts inventory) endpoints."""

from __future__ import annotations

import json
import platform
from typing import Any, Iterator
from urllib.parse import urlsplit

import requests

from . import auth
from .config import Settings, load_settings

_USER_AGENT = f"henley/0.1.0 (python {platform.python_version()})"


class JLCError(RuntimeError):
    """Raised when the API returns a non-success envelope."""

    def __init__(self, code: Any, message: str, payload: Any = None):
        super().__init__(f"JLC API error [{code}]: {message}")
        self.code = code
        self.message = message
        self.payload = payload


class JLCClient:
    """Thin signed client for the JLCPCB OpenAPI.

    Only the read-only component endpoints are implemented for now; order
    placement (PCB/TDP) can be layered on using the same ``_post`` plumbing.
    """

    def __init__(self, settings: Settings | None = None, *, timeout: float = 30.0):
        self.settings = settings or load_settings()
        self.timeout = timeout
        self._session = requests.Session()

    # -- low level -------------------------------------------------------
    def _post(self, uri: str, body: dict[str, Any] | None = None) -> Any:
        """Sign and POST a JSON request, returning the ``data`` payload."""
        endpoint = self.settings.endpoint
        url = endpoint + uri
        # Omit null fields, matching the Java SDK's toJSON() behaviour.
        clean = {k: v for k, v in (body or {}).items() if v is not None}
        payload = json.dumps(clean, separators=(",", ":"))

        cred = self.settings.credentials
        canonical_uri = urlsplit(url).path  # POST bodies carry no query string
        header = auth.authorization_header(
            app_id=cred.app_id,
            access_key=cred.access_key,
            secret_key=cred.secret_key,
            method="POST",
            canonical_uri=canonical_uri,
            payload=payload,
        )
        resp = self._session.post(
            url,
            data=payload.encode("utf-8"),
            headers={
                "Authorization": header,
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": _USER_AGENT,
            },
            timeout=self.timeout,
        )
        # JLC returns its JSON envelope ({code, success, message, data}) even on
        # HTTP 401/403, so parse it before deferring to HTTP-level errors.
        try:
            envelope = resp.json()
        except ValueError:
            resp.raise_for_status()
            raise
        return _unwrap(envelope)

    # -- component (parts inventory) endpoints ---------------------------
    def get_component_library_list(self, *, page_size: int = 30, last_key: str | None = None) -> dict:
        """One page of the JLC assembly component library (cursor-paginated)."""
        return self._post(
            "/overseas/openapi/component/getComponentLibraryList",
            {"pageSize": page_size, "lastKey": last_key},
        )

    def get_component_detail_by_code(self, codes: list[str]) -> list[dict]:
        """Full detail (price tiers, stock, parameters, datasheet) by component code."""
        return self._post(
            "/overseas/openapi/component/getComponentDetailByCode",
            {"componentCodes": list(codes)},
        )

    def get_component_infos(self, *, last_key: str | None = None) -> dict:
        """Bulk component info stream (LCSC part, package, stock, price)."""
        return self._post(
            "/overseas/openapi/component/getComponentInfos",
            {"lastKey": last_key},
        )

    def get_private_component_library(self, *, current_page: int = 1, page_size: int = 30) -> list[dict]:
        """Your private/consigned inventory held at JLCPCB."""
        return self._post(
            "/overseas/openapi/component/getPrivateComponentLibrary",
            {"currentPage": current_page, "pageSize": page_size},
        )

    # -- convenience iterators -------------------------------------------
    def iter_component_library(self, *, page_size: int = 100) -> Iterator[dict]:
        """Iterate the entire assembly library, following the ``lastKey`` cursor."""
        last_key = None
        while True:
            data = self.get_component_library_list(page_size=page_size, last_key=last_key)
            rows = (data or {}).get("componentLibraryInfoVOS") or []
            for row in rows:
                yield row
            last_key = (data or {}).get("lastKey")
            if not last_key or not rows:
                return


def _unwrap(envelope: Any) -> Any:
    """Validate the ``{code, success, message, data}`` envelope and return ``data``."""
    if not isinstance(envelope, dict):
        return envelope
    code = envelope.get("code", envelope.get("status"))
    message = envelope.get("message") or envelope.get("msg") or ""
    success = envelope.get("success")
    if success is True or code in (200, "200", 0, "0"):
        return envelope.get("data")
    if success is False or code is not None:
        raise JLCError(code, message, envelope.get("data"))
    return envelope.get("data")

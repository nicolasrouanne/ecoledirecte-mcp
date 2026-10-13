"""Low-level HTTP access to the École Directe API.

The API speaks form-encoded `data=<json>` bodies, answers HTTP 200 with its own
`code` field, and rotates the session token through the `x-token` header.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import httpx

from .errors import TransportError

API_URL = "https://api.ecoledirecte.com/v3"
API_VERSION = "4.102.0"

DEFAULT_HEADERS = {
    "accept": "application/json, text/plain, */*",
    "content-type": "application/x-www-form-urlencoded",
    "origin": "https://www.ecoledirecte.com",
    "referer": "https://www.ecoledirecte.com/",
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36"
    ),
}


class Code:
    """Values of the `code` field of API responses."""

    OK = 200
    NO_DATA = 210
    QCM_REQUIRED = 250
    INVALID_CREDENTIALS = 505
    INVALID_TOKEN = 520
    EXPIRED_TOKEN = 525


@dataclass(frozen=True)
class ApiResponse:
    code: int | None
    message: str | None
    data: Any

    @property
    def ok(self) -> bool:
        return self.code in (Code.OK, Code.NO_DATA)

    @property
    def token_rejected(self) -> bool:
        return self.code in (Code.INVALID_TOKEN, Code.EXPIRED_TOKEN)


class Transport:
    """Sends API requests, keeping the session token and GTK cookie up to date."""

    def __init__(self, http: httpx.Client | None = None, api_version: str = API_VERSION) -> None:
        self._http = http or httpx.Client(base_url=API_URL, timeout=60)
        self._http.headers.update(DEFAULT_HEADERS)
        self._api_version = api_version

    def close(self) -> None:
        self._http.close()

    def reset_session(self) -> None:
        for header in ("x-token", "x-gtk"):
            self._http.headers.pop(header, None)
        self._http.cookies.clear()

    def fetch_gtk(self) -> None:
        """Get the GTK cookie the login request must echo in its `x-gtk` header."""
        self._http.headers.pop("x-gtk", None)
        try:
            response = self._http.get("/login.awp", params={"gtk": 1, "v": self._api_version})
            response.raise_for_status()
        except httpx.HTTPError as error:
            raise TransportError(f"login.awp: {error}") from error
        gtk = response.cookies.get("GTK")
        if not gtk:
            raise TransportError("login.awp returned no GTK cookie")
        self._http.headers["x-gtk"] = gtk

    def drop_gtk(self) -> None:
        self._http.headers.pop("x-gtk", None)

    def post(
        self, path: str, data: dict[str, Any] | None = None, **params: str | int
    ) -> ApiResponse:
        try:
            response = self._http.post(
                path,
                params={**params, "v": self._api_version},
                content=f"data={json.dumps(data or {})}",
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as error:
            raise TransportError(f"{path}: {error}") from error
        if token := response.headers.get("x-token"):
            self._http.headers["x-token"] = token
        return ApiResponse(
            code=payload.get("code"), message=payload.get("message"), data=payload.get("data")
        )

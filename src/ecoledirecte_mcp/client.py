"""Minimal client for the private École Directe API (v3).

Login flow, borrowed from hacf-fr/ecoledirecte_api and Ecole-Directe-Plus:

1. GET login.awp?gtk=1 sets a GTK cookie, echoed back in the X-Gtk header.
2. POST login.awp with the credentials. Code 250 means École Directe sees a
   new device and asks a security question (QCM) via connexion/doubleauth.awp.
3. Answering it returns a cn/cv pair identifying this device. Sent back in the
   "fa" field of later logins, it skips the QCM. Repeated QCM logins count
   towards the account lockout, so the pair is persisted in the state file.
"""

from __future__ import annotations

import base64
import html
import json
import os
import re
import urllib.parse
from collections.abc import Callable
from datetime import date
from pathlib import Path

import httpx

API_URL = "https://api.ecoledirecte.com/v3"
API_VERSION = "4.102.0"

OK = 200
NO_DATA = 210
QCM_REQUIRED = 250
TOKEN_ERRORS = (520, 525)

FOLDERS = {"inbox": "received", "archived": "archived", "sent": "sent"}

HEADERS = {
    "accept": "application/json, text/plain, */*",
    "content-type": "application/x-www-form-urlencoded",
    "origin": "https://www.ecoledirecte.com",
    "referer": "https://www.ecoledirecte.com/",
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36"
    ),
}


class EcoleDirecteError(Exception):
    pass


class QCMRequired(EcoleDirecteError):
    """This device is not trusted yet: run `ecoledirecte-mcp login` once."""


def default_state_path() -> Path:
    base = os.environ.get("XDG_STATE_HOME") or Path.home() / ".local" / "state"
    return Path(base) / "ecoledirecte-mcp" / "state.json"


def school_year(today: date | None = None) -> str:
    today = today or date.today()
    start = today.year if today.month >= 8 else today.year - 1
    return f"{start}-{start + 1}"


def html_to_text(raw: str) -> str:
    text = re.sub(r"(?i)<br\s*/?>|</(p|div|li|tr|h\d)>", "\n", raw)
    text = html.unescape(re.sub(r"<[^>]+>", "", text))
    return re.sub(r"\n{3,}", "\n\n", text.replace("\xa0", " ")).strip()


def _quote(value: str) -> str:
    return urllib.parse.quote(value, safe="~()*!.'")


class EcoleDirecteClient:
    def __init__(self, username: str, password: str, state_path: Path | None = None):
        self.username = username
        self.password = password
        self.state_path = state_path or default_state_path()
        self.http = httpx.Client(base_url=API_URL, headers=HEADERS, timeout=60)
        self.token: str | None = None
        self.account: dict | None = None

    # -- state -------------------------------------------------------------

    def _load_state(self) -> dict:
        try:
            return json.loads(self.state_path.read_text())
        except FileNotFoundError:
            return {}

    def _save_state(self, state: dict) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.touch(mode=0o600, exist_ok=True)
        self.state_path.write_text(json.dumps(state, indent=2))

    # -- transport ---------------------------------------------------------

    def _send(self, path: str, params: dict, data: dict | str) -> tuple[dict, httpx.Response]:
        body = data if isinstance(data, str) else json.dumps(data)
        response = self.http.post(path, params={**params, "v": API_VERSION}, content=f"data={body}")
        if token := response.headers.get("x-token"):
            self.token = token
            self.http.headers["x-token"] = token
        try:
            payload = response.json()
        except ValueError as error:
            raise EcoleDirecteError(f"{path}: HTTP {response.status_code}") from error
        return payload, response

    def _call(self, path: str, params: dict, data: dict) -> dict:
        if self.token is None:
            self.login()
        payload, _ = self._send(path, params, data)
        if payload.get("code") in TOKEN_ERRORS:
            self.login()
            payload, _ = self._send(path, params, data)
        if payload.get("code") not in (OK, NO_DATA):
            raise EcoleDirecteError(f"{path}: {payload.get('code')} {payload.get('message')}")
        return payload.get("data") or {}

    # -- login -------------------------------------------------------------

    def _gtk(self) -> None:
        self.http.headers.pop("x-gtk", None)
        response = self.http.get("/login.awp", params={"gtk": 1, "v": API_VERSION})
        gtk = response.cookies.get("GTK")
        if not gtk:
            raise EcoleDirecteError("No GTK cookie returned by login.awp")
        self.http.headers["x-gtk"] = gtk

    def _login_request(self, fa: dict | None) -> dict:
        self._gtk()
        data = {
            "identifiant": _quote(self.username),
            "motdepasse": _quote(self.password),
            "isReLogin": False,
            "uuid": "",
            **(fa or {}),
            "fa": [fa] if fa else [],
        }
        payload, _ = self._send("/login.awp", {}, data)
        self.http.headers.pop("x-gtk", None)
        return payload

    def login(self, answer: Callable[[str, list[str]], str] | None = None) -> dict:
        """Log in, reusing the trusted device if any.

        `answer(question, propositions)` picks the QCM answer when École
        Directe asks for one. Without it, a QCM raises QCMRequired.
        """
        self.http.headers.pop("x-token", None)
        state = self._load_state()
        fa = state.get("fa")
        payload = self._login_request(fa)

        if payload.get("code") == QCM_REQUIRED:
            if answer is None:
                raise QCMRequired(
                    "École Directe asks for its security question: "
                    "run `ecoledirecte-mcp login` in a terminal."
                )
            qcm, _ = self._send("/connexion/doubleauth.awp", {"verbe": "get"}, "{}")
            question = base64.b64decode(qcm["data"]["question"]).decode()
            propositions = [base64.b64decode(p).decode() for p in qcm["data"]["propositions"]]
            choice = answer(question, propositions)
            encoded = base64.b64encode(choice.encode()).decode()
            result, _ = self._send(
                "/connexion/doubleauth.awp", {"verbe": "post"}, {"choix": encoded}
            )
            if result.get("code") != OK:
                raise EcoleDirecteError(f"Wrong answer to the security question: {result}")
            fa = {"cn": result["data"]["cn"], "cv": result["data"]["cv"]}
            self._save_state({**state, "fa": fa})
            payload = self._login_request(fa)

        if payload.get("code") != OK:
            raise EcoleDirecteError(f"Login failed: {payload.get('code')} {payload.get('message')}")

        accounts = payload["data"]["accounts"]
        self.account = next((a for a in accounts if a.get("main")), accounts[0])
        return self.account

    # -- messaging -----------------------------------------------------------

    @property
    def _owner(self) -> str:
        if self.account is None:
            self.login()
        kind = "eleves" if self.account["typeCompte"] == "E" else "familles"
        return f"/{kind}/{self.account['id']}"

    def list_messages(self, folder: str = "inbox") -> list[dict]:
        kind = FOLDERS[folder]
        data = self._call(
            f"{self._owner}/messages.awp",
            {
                "force": "false",
                "typeRecuperation": kind,
                "idClasseur": 0,
                "orderBy": "date",
                "order": "desc",
                "query": "",
                "onlyRead": "",
                "getAll": 1,
                "verbe": "get",
            },
            {"anneeMessages": school_year()},
        )
        return [
            {
                "id": m["id"],
                "date": m.get("date"),
                "from": _person(m.get("from")),
                "subject": m.get("subject"),
                "read": m.get("read"),
                "attachments": len(m.get("files") or []),
            }
            for m in (data.get("messages") or {}).get(kind, [])
        ]

    def read_message(self, message_id: int, sent: bool = False) -> dict:
        """Fetch a message. École Directe marks it as read on its side."""
        data = self._call(
            f"{self._owner}/messages/{message_id}.awp",
            {"verbe": "get", "mode": "expediteur" if sent else "destinataire"},
            {"anneeMessages": school_year()},
        )
        content = base64.b64decode(data.get("content") or "").decode(errors="replace")
        return {
            "id": data.get("id"),
            "date": data.get("date"),
            "from": _person(data.get("from")),
            "subject": data.get("subject"),
            "body": html_to_text(content),
            "attachments": [f.get("libelle") for f in data.get("files") or []],
        }

    def archive_messages(self, ids: list[int]) -> None:
        if ids:
            self._call(
                f"{self._owner}/messages.awp",
                {"verbe": "put"},
                {"action": "archiver", "ids": ids, "anneeMessages": school_year()},
            )


def _person(person: dict | None) -> str | None:
    if not person:
        return None
    parts = (person.get("civilite"), person.get("prenom"), person.get("nom"))
    name = " ".join(p for p in parts if p)
    return name or person.get("name")

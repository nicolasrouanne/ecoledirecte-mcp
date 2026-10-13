"""An in-memory École Directe API, served through httpx.MockTransport."""

from __future__ import annotations

import base64
import json
import urllib.parse
from dataclasses import dataclass, field
from typing import Any

import httpx

from ecoledirecte_mcp.transport import API_URL

ACCOUNT_ID = 42
GTK = "gtk-cookie"
QUESTION = "Quel est votre mois de naissance ?"
CHOICES = ["Janvier", "Mars", "Juin"]
ANSWER = "Mars"
DEVICE = {"cn": "device-cn", "cv": "device-cv"}


def b64(value: str) -> str:
    return base64.b64encode(value.encode()).decode()


@dataclass
class FakeEcoleDirecte:
    username: str = "parent"
    password: str = "s3cret&pass"
    messages: list[dict[str, Any]] = field(default_factory=list)
    archived_ids: list[int] = field(default_factory=list)
    logins: int = 0
    qcm_asked: int = 0
    expire_token_once: bool = False
    _token_count: int = 0
    _valid_token: str | None = None

    def client(self) -> httpx.Client:
        return httpx.Client(base_url=API_URL, transport=httpx.MockTransport(self.handle))

    def handle(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path.removeprefix("/v3")
        verb = request.url.params.get("verbe")
        if path == "/login.awp" and request.method == "GET":
            return httpx.Response(200, headers={"set-cookie": f"GTK={GTK}; Path=/"}, json={})
        body = self._body(request)
        if path == "/login.awp":
            return self._login(request, body)
        if path == "/connexion/doubleauth.awp":
            return self._doubleauth(verb, body)
        if request.headers.get("x-token") != self._valid_token:
            return self._reply(520, message="Token invalide")
        if self.expire_token_once:
            self.expire_token_once = False
            return self._reply(525, message="Token expiré")
        if path == f"/familles/{ACCOUNT_ID}/messages.awp" and verb == "get":
            kind = request.url.params["typeRecuperation"]
            return self._reply(200, {"messages": {kind: self.messages}})
        if path == f"/familles/{ACCOUNT_ID}/messages.awp" and verb == "put":
            assert body["action"] == "archiver"
            self.archived_ids.extend(body["ids"])
            return self._reply(200)
        if path.startswith(f"/familles/{ACCOUNT_ID}/messages/"):
            message_id = int(path.rsplit("/", 1)[1].removesuffix(".awp"))
            return self._reply(200, self._detail(message_id))
        return self._reply(404, message=f"Unknown route {path}")

    def _login(self, request: httpx.Request, body: dict[str, Any]) -> httpx.Response:
        assert request.headers.get("x-gtk") == GTK
        username = urllib.parse.unquote(body["identifiant"])
        password = urllib.parse.unquote(body["motdepasse"])
        if (username, password) != (self.username, self.password):
            return self._reply(505, message="Identifiant et/ou mot de passe invalide !")
        if body.get("fa") != [DEVICE]:
            return self._reply(250, message="QCM", token=True)
        self.logins += 1
        account = {"id": ACCOUNT_ID, "typeCompte": "1", "main": True, "prenom": "Alex"}
        return self._reply(200, {"accounts": [account]}, token=True, valid=True)

    def _doubleauth(self, verb: str | None, body: dict[str, Any]) -> httpx.Response:
        if verb == "get":
            self.qcm_asked += 1
            return self._reply(200, {"question": b64(QUESTION), "propositions": map_b64(CHOICES)})
        if body.get("choix") == b64(ANSWER):
            return self._reply(200, DEVICE)
        return self._reply(520, message="Mauvaise réponse")

    def _detail(self, message_id: int) -> dict[str, Any]:
        summary = next(m for m in self.messages if m["id"] == message_id)
        return {**summary, "content": b64("<p>Bonjour,</p><p>Sortie&nbsp;le <b>lundi</b>.</p>")}

    @staticmethod
    def _body(request: httpx.Request) -> dict[str, Any]:
        raw = request.content.decode()
        assert raw.startswith("data=")
        parsed: dict[str, Any] = json.loads(raw.removeprefix("data="))
        return parsed

    def _reply(
        self,
        code: int,
        data: Any = None,
        message: str = "",
        token: bool = False,
        valid: bool = False,
    ) -> httpx.Response:
        headers = {}
        if token:
            self._token_count += 1
            headers["x-token"] = f"token-{self._token_count}"
            if valid:
                self._valid_token = headers["x-token"]
        payload = {"code": code, "message": message, "data": data}
        return httpx.Response(200, headers=headers, json=payload)


def map_b64(values: list[str]) -> list[str]:
    return [b64(value) for value in values]


def raw_message(message_id: int, *, read: bool, subject: str = "Sortie") -> dict[str, Any]:
    return {
        "id": message_id,
        "date": "2026-10-09 14:32:11",
        "subject": subject,
        "read": read,
        "from": {"civilite": "Mme", "prenom": "Claire", "nom": "Martin"},
        "files": [{"libelle": "autorisation.pdf"}],
    }

"""Login flow, borrowed from hacf-fr/ecoledirecte_api and Ecole-Directe-Plus.

1. GET login.awp?gtk=1 sets a GTK cookie, echoed in the `x-gtk` header.
2. POST login.awp with the credentials. Code 250 means École Directe sees a new
   device and asks a security question (QCM) via connexion/doubleauth.awp.
3. The right answer returns a cn/cv pair identifying this device. Sent back in
   the `fa` field of later logins, it skips the question. Logins that need the
   question count towards the account lockout, so the pair is persisted.
"""

from __future__ import annotations

import base64
import urllib.parse
from dataclasses import dataclass
from typing import Any, Protocol

from .errors import AuthenticationError, QCMRequiredError
from .models import Account, TrustedDevice
from .storage import TrustedDeviceStore
from .transport import ApiResponse, Code, Transport


@dataclass(frozen=True)
class Credentials:
    username: str
    password: str


class QCMSolver(Protocol):
    def __call__(self, question: str, choices: list[str]) -> str:
        """Return the chosen answer, one of `choices`."""
        ...


class Authenticator:
    def __init__(
        self, transport: Transport, credentials: Credentials, store: TrustedDeviceStore
    ) -> None:
        self._transport = transport
        self._credentials = credentials
        self._store = store

    def login(self, solver: QCMSolver | None = None) -> Account:
        """Open a session, answering the security question with `solver` if asked."""
        device = self._store.load()
        response = self._submit_credentials(device)

        if response.code == Code.QCM_REQUIRED:
            if solver is None:
                raise QCMRequiredError()
            device = self._answer_qcm(solver)
            self._store.save(device)
            response = self._submit_credentials(device)

        if response.code == Code.INVALID_CREDENTIALS:
            raise AuthenticationError("Invalid username or password.")
        if not response.ok or not response.data:
            raise AuthenticationError(f"Login failed: code {response.code} ({response.message})")
        return self._main_account(response.data["accounts"])

    def _submit_credentials(self, device: TrustedDevice | None) -> ApiResponse:
        self._transport.reset_session()
        self._transport.fetch_gtk()
        fa = device.model_dump() if device else None
        payload = {
            "identifiant": _encode(self._credentials.username),
            "motdepasse": _encode(self._credentials.password),
            "isReLogin": False,
            "uuid": "",
            **(fa or {}),
            "fa": [fa] if fa else [],
        }
        try:
            return self._transport.post("/login.awp", payload)
        finally:
            self._transport.drop_gtk()

    def _answer_qcm(self, solver: QCMSolver) -> TrustedDevice:
        qcm = self._transport.post("/connexion/doubleauth.awp", verbe="get")
        if not qcm.ok:
            raise AuthenticationError(f"Could not fetch the security question: {qcm.message}")
        question = _b64decode(qcm.data["question"])
        choices = [_b64decode(choice) for choice in qcm.data["propositions"]]

        answer = solver(question, choices)
        if answer not in choices:
            raise AuthenticationError(f"{answer!r} is not one of the proposed answers.")

        result = self._transport.post(
            "/connexion/doubleauth.awp", {"choix": _b64encode(answer)}, verbe="post"
        )
        if not result.ok:
            raise AuthenticationError("Wrong answer to the security question.")
        return TrustedDevice(cn=result.data["cn"], cv=result.data["cv"])

    @staticmethod
    def _main_account(accounts: list[dict[str, Any]]) -> Account:
        main = next((account for account in accounts if account.get("main")), accounts[0])
        return Account.from_api(main)


def _encode(value: str) -> str:
    """Credentials are percent-encoded inside the JSON, as the web app does."""
    return urllib.parse.quote(value, safe="~()*!.'")


def _b64decode(value: str) -> str:
    return base64.b64decode(value).decode()


def _b64encode(value: str) -> str:
    return base64.b64encode(value.encode()).decode()

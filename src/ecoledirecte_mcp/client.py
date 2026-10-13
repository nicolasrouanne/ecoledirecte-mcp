"""High-level client: an authenticated session and the services built on it."""

from __future__ import annotations

from types import TracebackType
from typing import Any, Self

from .auth import Authenticator, Credentials, QCMSolver
from .errors import APIError
from .messaging import MessagingService
from .models import Account
from .storage import TrustedDeviceStore
from .transport import Transport


class EcoleDirecteClient:
    """Logs in lazily and renews the session when École Directe rejects the token."""

    def __init__(
        self,
        credentials: Credentials,
        store: TrustedDeviceStore | None = None,
        transport: Transport | None = None,
    ) -> None:
        self._transport = transport or Transport()
        self._authenticator = Authenticator(
            self._transport, credentials, store or TrustedDeviceStore()
        )
        self._account: Account | None = None
        self.messages = MessagingService(self)

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        self._transport.close()

    def login(self, solver: QCMSolver | None = None) -> Account:
        self._account = self._authenticator.login(solver)
        return self._account

    @property
    def account(self) -> Account:
        if self._account is None:
            return self.login()
        return self._account

    def request(self, path: str, data: dict[str, Any] | None = None, **params: str | int) -> Any:
        """POST an account-scoped request and return its `data`, raising on API errors."""
        account = self.account
        response = self._transport.post(account.api_path + path, data, **params)
        if response.token_rejected:
            account = self.login()
            response = self._transport.post(account.api_path + path, data, **params)
        if not response.ok:
            raise APIError(path, response.code, response.message)
        return response.data or {}

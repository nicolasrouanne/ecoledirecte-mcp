"""Exceptions raised by the École Directe client."""

from __future__ import annotations


class EcoleDirecteError(Exception):
    """Base class for every error raised by this package."""


class AuthenticationError(EcoleDirecteError):
    """The credentials were rejected, or the login flow failed."""


class QCMRequiredError(AuthenticationError):
    """École Directe asks its security question and no solver was given."""

    def __init__(self) -> None:
        super().__init__(
            "École Directe asks for its security question: "
            "run `ecoledirecte-mcp login` in a terminal to trust this device."
        )


class TransportError(EcoleDirecteError):
    """École Directe could not be reached, or answered something unexpected."""


class APIError(EcoleDirecteError):
    """École Directe answered with a non-success code."""

    def __init__(self, path: str, code: int | None, message: str | None) -> None:
        super().__init__(f"{path}: code {code} ({message or 'no message'})")
        self.path = path
        self.code = code
        self.message = message

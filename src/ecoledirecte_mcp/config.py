"""Configuration from the environment."""

from __future__ import annotations

import os

from .auth import Credentials
from .errors import EcoleDirecteError

USERNAME_VAR = "ECOLEDIRECTE_USERNAME"
PASSWORD_VAR = "ECOLEDIRECTE_PASSWORD"


def credentials_from_env() -> Credentials:
    missing = [var for var in (USERNAME_VAR, PASSWORD_VAR) if not os.environ.get(var)]
    if missing:
        raise EcoleDirecteError(f"Missing environment variable(s): {', '.join(missing)}")
    return Credentials(os.environ[USERNAME_VAR], os.environ[PASSWORD_VAR])

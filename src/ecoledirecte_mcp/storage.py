"""Persistence of the trusted device between runs."""

from __future__ import annotations

import os
from pathlib import Path

from .models import TrustedDevice


def default_state_dir() -> Path:
    base = os.environ.get("XDG_STATE_HOME")
    return (Path(base) if base else Path.home() / ".local" / "state") / "ecoledirecte-mcp"


class TrustedDeviceStore:
    """Stores the trusted device as JSON, readable by the current user only."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or default_state_dir() / "trusted_device.json"

    def load(self) -> TrustedDevice | None:
        try:
            return TrustedDevice.model_validate_json(self.path.read_text())
        except FileNotFoundError:
            return None

    def save(self, device: TrustedDevice) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.touch(mode=0o600, exist_ok=True)
        self.path.write_text(device.model_dump_json(indent=2))

    def clear(self) -> None:
        self.path.unlink(missing_ok=True)

from __future__ import annotations

from pathlib import Path

import pytest

from ecoledirecte_mcp.auth import Credentials
from ecoledirecte_mcp.client import EcoleDirecteClient
from ecoledirecte_mcp.models import TrustedDevice
from ecoledirecte_mcp.storage import TrustedDeviceStore
from ecoledirecte_mcp.transport import Transport

from .fake_api import ANSWER, DEVICE, FakeEcoleDirecte, raw_message


@pytest.fixture
def api() -> FakeEcoleDirecte:
    return FakeEcoleDirecte(messages=[raw_message(1, read=True), raw_message(2, read=False)])


@pytest.fixture
def store(tmp_path: Path) -> TrustedDeviceStore:
    return TrustedDeviceStore(tmp_path / "trusted_device.json")


@pytest.fixture
def trusted_store(store: TrustedDeviceStore) -> TrustedDeviceStore:
    store.save(TrustedDevice(**DEVICE))
    return store


@pytest.fixture
def make_client(api: FakeEcoleDirecte):  # type: ignore[no-untyped-def]
    def make(store: TrustedDeviceStore, password: str | None = None) -> EcoleDirecteClient:
        credentials = Credentials(api.username, password or api.password)
        return EcoleDirecteClient(credentials, store, Transport(api.client()))

    return make


@pytest.fixture
def client(make_client, trusted_store: TrustedDeviceStore) -> EcoleDirecteClient:  # type: ignore[no-untyped-def]
    return make_client(trusted_store)  # type: ignore[no-any-return]


def pick_answer(question: str, choices: list[str]) -> str:
    return ANSWER

from __future__ import annotations

import pytest

from ecoledirecte_mcp.errors import AuthenticationError, QCMRequiredError
from ecoledirecte_mcp.models import AccountKind, TrustedDevice
from ecoledirecte_mcp.storage import TrustedDeviceStore

from .conftest import pick_answer
from .fake_api import DEVICE, FakeEcoleDirecte


def test_trusted_device_skips_the_security_question(
    api: FakeEcoleDirecte, make_client, trusted_store: TrustedDeviceStore
) -> None:
    account = make_client(trusted_store).login()

    assert account.id == 42
    assert account.kind is AccountKind.FAMILY
    assert api.qcm_asked == 0


def test_security_question_is_answered_once_then_device_is_trusted(
    api: FakeEcoleDirecte, make_client, store: TrustedDeviceStore
) -> None:
    make_client(store).login(pick_answer)

    assert api.qcm_asked == 1
    assert store.load() == TrustedDevice(**DEVICE)


def test_security_question_without_solver_raises(make_client, store: TrustedDeviceStore) -> None:
    with pytest.raises(QCMRequiredError):
        make_client(store).login()


def test_answer_outside_the_choices_is_rejected(make_client, store: TrustedDeviceStore) -> None:
    with pytest.raises(AuthenticationError, match="not one of the proposed answers"):
        make_client(store).login(lambda question, choices: "Décembre")


def test_wrong_password_raises(make_client, trusted_store: TrustedDeviceStore) -> None:
    with pytest.raises(AuthenticationError, match="Invalid username or password"):
        make_client(trusted_store, password="wrong").login()


def test_store_file_is_private(trusted_store: TrustedDeviceStore) -> None:
    assert trusted_store.path.stat().st_mode & 0o777 == 0o600

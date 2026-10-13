from __future__ import annotations

from datetime import datetime

import pytest

from ecoledirecte_mcp.client import EcoleDirecteClient
from ecoledirecte_mcp.errors import APIError
from ecoledirecte_mcp.models import Folder

from .fake_api import FakeEcoleDirecte


def test_list_folder_parses_messages(client: EcoleDirecteClient) -> None:
    messages = client.messages.list_folder(Folder.INBOX)

    assert [message.id for message in messages] == [1, 2]
    first = messages[0]
    assert first.read is True
    assert first.sender == "Mme Claire Martin"
    assert first.date == datetime(2026, 10, 9, 14, 32, 11)
    assert first.attachment_count == 1


def test_get_returns_the_body_as_text(client: EcoleDirecteClient) -> None:
    detail = client.messages.get(1)

    assert detail.body == "Bonjour,\nSortie le lundi."
    assert detail.attachments == ["autorisation.pdf"]


def test_archive_sends_the_ids(api: FakeEcoleDirecte, client: EcoleDirecteClient) -> None:
    assert client.messages.archive([1, 3]) == [1, 3]
    assert api.archived_ids == [1, 3]


def test_archive_nothing_makes_no_request(
    api: FakeEcoleDirecte, client: EcoleDirecteClient
) -> None:
    assert client.messages.archive([]) == []
    assert api.logins == 0


def test_expired_token_triggers_a_new_login(
    api: FakeEcoleDirecte, client: EcoleDirecteClient
) -> None:
    client.login()
    api.expire_token_once = True

    assert len(client.messages.list_folder()) == 2
    assert api.logins == 2


def test_api_error_is_raised(client: EcoleDirecteClient) -> None:
    with pytest.raises(APIError, match="code 404"):
        client.request("/unknown.awp")

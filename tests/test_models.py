from __future__ import annotations

from datetime import date

import pytest

from ecoledirecte_mcp.html import html_to_text
from ecoledirecte_mcp.models import Account, AccountKind, Folder


@pytest.mark.parametrize(
    ("today", "expected"),
    [
        (date(2026, 10, 13), "2026-2027"),
        (date(2027, 3, 1), "2026-2027"),
        (date(2027, 8, 25), "2027-2028"),
    ],
)
def test_school_year_starts_in_august(today: date, expected: str) -> None:
    account = Account(id=1, kind=AccountKind.FAMILY)
    assert account.current_school_year(today) == expected


def test_school_year_from_the_api_wins() -> None:
    account = Account(id=1, kind=AccountKind.FAMILY, school_year="2025-2026")
    assert account.current_school_year(date(2026, 10, 13)) == "2025-2026"


def test_account_api_path() -> None:
    assert Account.from_api({"id": 7, "typeCompte": "E"}).api_path == "/eleves/7"
    assert Account.from_api({"id": 7, "typeCompte": "1"}).api_path == "/familles/7"


def test_inbox_maps_to_received() -> None:
    assert Folder.INBOX.api_name == "received"
    assert Folder.ARCHIVED.api_name == "archived"


def test_html_to_text() -> None:
    markup = "<div>Bonjour&nbsp;!<br>Liste :</div><ul><li>stylo</li><li>cahier</li></ul>"
    assert html_to_text(markup) == "Bonjour !\nListe :\n- stylo\n- cahier"

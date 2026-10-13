"""Domain models, parsed from the raw École Directe payloads."""

from __future__ import annotations

import base64
from datetime import date, datetime
from enum import StrEnum
from typing import Any, Self

from pydantic import BaseModel, ConfigDict

from .html import html_to_text


class Folder(StrEnum):
    INBOX = "inbox"
    ARCHIVED = "archived"
    SENT = "sent"

    @property
    def api_name(self) -> str:
        """The `typeRecuperation` value, also the key of the messages in the response."""
        return "received" if self is Folder.INBOX else self.value


class AccountKind(StrEnum):
    STUDENT = "E"
    FAMILY = "1"


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True)


class TrustedDevice(_Model):
    """The cn/cv pair École Directe returns once its security question is answered."""

    cn: str
    cv: str


class Account(_Model):
    id: int
    kind: AccountKind
    first_name: str | None = None
    last_name: str | None = None
    school_year: str | None = None

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> Self:
        kind = AccountKind.STUDENT if payload["typeCompte"] == "E" else AccountKind.FAMILY
        return cls(
            id=payload["id"],
            kind=kind,
            first_name=payload.get("prenom"),
            last_name=payload.get("nom"),
            school_year=payload.get("anneeScolaireCourante") or None,
        )

    @property
    def api_path(self) -> str:
        """Prefix of the account-scoped routes."""
        prefix = "eleves" if self.kind is AccountKind.STUDENT else "familles"
        return f"/{prefix}/{self.id}"

    def current_school_year(self, today: date | None = None) -> str:
        """The `anneeMessages` value, e.g. `2026-2027`. School years start in August."""
        if self.school_year:
            return self.school_year
        today = today or date.today()
        start = today.year if today.month >= 8 else today.year - 1
        return f"{start}-{start + 1}"


class Message(_Model):
    id: int
    date: datetime | None
    sender: str | None
    subject: str
    read: bool
    attachment_count: int

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> Self:
        return cls(
            id=payload["id"],
            date=_parse_date(payload.get("date")),
            sender=_person_name(payload.get("from")),
            subject=payload.get("subject") or "",
            read=bool(payload.get("read")),
            attachment_count=len(payload.get("files") or []),
        )


class MessageDetail(_Model):
    id: int
    date: datetime | None
    sender: str | None
    subject: str
    body: str
    attachments: list[str]

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> Self:
        content = base64.b64decode(payload.get("content") or "").decode(errors="replace")
        return cls(
            id=payload["id"],
            date=_parse_date(payload.get("date")),
            sender=_person_name(payload.get("from")),
            subject=payload.get("subject") or "",
            body=html_to_text(content),
            attachments=[file.get("libelle", "") for file in payload.get("files") or []],
        )


def _parse_date(value: str | None) -> datetime | None:
    try:
        return datetime.fromisoformat(value) if value else None
    except ValueError:
        return None


def _person_name(person: dict[str, Any] | None) -> str | None:
    if not person:
        return None
    parts = (person.get("civilite"), person.get("prenom"), person.get("nom"))
    return " ".join(part for part in parts if part) or person.get("name")

"""The messaging module of École Directe."""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

from .models import Folder, Message, MessageDetail

if TYPE_CHECKING:
    from .client import EcoleDirecteClient


class MessagingService:
    def __init__(self, client: EcoleDirecteClient) -> None:
        self._client = client

    @property
    def _school_year(self) -> dict[str, str]:
        return {"anneeMessages": self._client.account.current_school_year()}

    def list_folder(self, folder: Folder = Folder.INBOX) -> list[Message]:
        """Messages of a folder, newest first."""
        data = self._client.request(
            "/messages.awp",
            self._school_year,
            verbe="get",
            typeRecuperation=folder.api_name,
            idClasseur=0,
            orderBy="date",
            order="desc",
            getAll=1,
        )
        raw_messages = (data.get("messages") or {}).get(folder.api_name, [])
        return [Message.from_api(raw) for raw in raw_messages]

    def get(self, message_id: int, *, sent: bool = False) -> MessageDetail:
        """A message with its body. École Directe marks it as read."""
        data = self._client.request(
            f"/messages/{message_id}.awp",
            self._school_year,
            verbe="get",
            mode="expediteur" if sent else "destinataire",
        )
        return MessageDetail.from_api(data)

    def archive(self, message_ids: Iterable[int]) -> list[int]:
        """Move messages to the archive, returning the ids sent."""
        ids = list(message_ids)
        if ids:
            self._client.request(
                "/messages.awp",
                {"action": "archiver", "ids": ids, **self._school_year},
                verbe="put",
            )
        return ids

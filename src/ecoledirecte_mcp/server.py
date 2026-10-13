"""MCP tools over the École Directe messaging."""

from __future__ import annotations

import functools
from collections.abc import Callable
from typing import ParamSpec, TypeVar

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import BaseModel

from .client import EcoleDirecteClient
from .errors import EcoleDirecteError
from .models import Folder, Message, MessageDetail

P = ParamSpec("P")
R = TypeVar("R")


class ArchiveResult(BaseModel):
    archived: bool
    messages: list[Message]


def _surface_errors(fn: Callable[P, R]) -> Callable[P, R]:
    """Report École Directe errors (bad login, security question) to the agent verbatim."""

    @functools.wraps(fn)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        try:
            return fn(*args, **kwargs)
        except EcoleDirecteError as error:
            raise ToolError(str(error)) from error

    return wrapper


def build_server(client_factory: Callable[[], EcoleDirecteClient]) -> MCPServer:
    """Build the server. The client is created on the first tool call, then reused."""
    get_client = functools.cache(client_factory)
    server = MCPServer("ecoledirecte")

    @server.tool()
    @_surface_errors
    def list_messages(
        folder: Folder = Folder.INBOX, unread_only: bool = False, limit: int = 50
    ) -> list[Message]:
        """List École Directe messages, newest first."""
        messages = get_client().messages.list_folder(folder)
        if unread_only:
            messages = [message for message in messages if not message.read]
        return messages[:limit]

    @server.tool()
    @_surface_errors
    def read_message(message_id: int, sent: bool = False) -> MessageDetail:
        """Read a message as plain text. This marks it as read in École Directe."""
        return get_client().messages.get(message_id, sent=sent)

    @server.tool()
    @_surface_errors
    def archive_messages(message_ids: list[int]) -> list[int]:
        """Move messages from the inbox to the archive. Returns the archived ids."""
        return get_client().messages.archive(message_ids)

    @server.tool()
    @_surface_errors
    def archive_read_messages(dry_run: bool = True) -> ArchiveResult:
        """Archive every inbox message already read. Dry run by default: only lists them."""
        messaging = get_client().messages
        read = [message for message in messaging.list_folder(Folder.INBOX) if message.read]
        if not dry_run:
            messaging.archive(message.id for message in read)
        return ArchiveResult(archived=not dry_run, messages=read)

    return server

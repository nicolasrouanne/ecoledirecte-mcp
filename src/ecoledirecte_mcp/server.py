"""MCP tools over the École Directe messaging."""

from __future__ import annotations

import functools
import os
from typing import Literal

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from .client import EcoleDirecteClient, EcoleDirecteError

mcp = MCPServer("ecoledirecte")
_client: EcoleDirecteClient | None = None


def client() -> EcoleDirecteClient:
    global _client
    if _client is None:
        _client = EcoleDirecteClient(
            os.environ["ECOLEDIRECTE_USERNAME"], os.environ["ECOLEDIRECTE_PASSWORD"]
        )
    return _client


def surface_errors(fn):
    """Report École Directe errors (bad login, QCM needed) to the agent verbatim."""

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except EcoleDirecteError as error:
            raise ToolError(str(error)) from error

    return wrapper


@mcp.tool()
@surface_errors
def list_messages(
    folder: Literal["inbox", "archived", "sent"] = "inbox",
    unread_only: bool = False,
    limit: int = 50,
) -> list[dict]:
    """List École Directe messages, newest first (id, date, from, subject, read, attachments)."""
    messages = client().list_messages(folder)
    if unread_only:
        messages = [m for m in messages if not m["read"]]
    return messages[:limit]


@mcp.tool()
@surface_errors
def read_message(message_id: int, sent: bool = False) -> dict:
    """Read a message as plain text. This marks it as read in École Directe."""
    return client().read_message(message_id, sent=sent)


@mcp.tool()
@surface_errors
def archive_messages(message_ids: list[int]) -> str:
    """Move the given messages from the inbox to the archive."""
    client().archive_messages(message_ids)
    return f"Archived {len(message_ids)} message(s)."


@mcp.tool()
@surface_errors
def archive_read_messages(dry_run: bool = True) -> dict:
    """Archive every inbox message already read. Defaults to a dry run listing them."""
    read = [m for m in client().list_messages("inbox") if m["read"]]
    if not dry_run:
        client().archive_messages([m["id"] for m in read])
    return {"archived": not dry_run, "count": len(read), "messages": read}

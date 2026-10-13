from __future__ import annotations

import json

import anyio
from mcp import Client

from ecoledirecte_mcp.client import EcoleDirecteClient
from ecoledirecte_mcp.server import build_server

from .fake_api import FakeEcoleDirecte


def call(client: EcoleDirecteClient, tool: str, arguments: dict[str, object]):  # type: ignore[no-untyped-def]
    async def run():  # type: ignore[no-untyped-def]
        async with Client(build_server(lambda: client)) as mcp:
            return await mcp.call_tool(tool, arguments)

    return anyio.run(run)


def test_tools_are_exposed(client: EcoleDirecteClient) -> None:
    async def run() -> list[str]:
        async with Client(build_server(lambda: client)) as mcp:
            return [tool.name for tool in (await mcp.list_tools()).tools]

    assert anyio.run(run) == [
        "list_messages",
        "read_message",
        "archive_messages",
        "archive_read_messages",
    ]


def test_list_unread_messages(client: EcoleDirecteClient) -> None:
    result = call(client, "list_messages", {"unread_only": True})
    assert [m["id"] for m in result.structured_content["result"]] == [2]


def test_archive_read_messages_is_a_dry_run_by_default(
    api: FakeEcoleDirecte, client: EcoleDirecteClient
) -> None:
    result = call(client, "archive_read_messages", {})
    assert result.structured_content["archived"] is False
    assert api.archived_ids == []

    call(client, "archive_read_messages", {"dry_run": False})
    assert api.archived_ids == [1]


def test_errors_reach_the_agent(make_client, store) -> None:  # type: ignore[no-untyped-def]
    result = call(make_client(store), "list_messages", {})
    assert result.is_error
    assert "ecoledirecte-mcp login" in json.dumps(result.model_dump(mode="json"))

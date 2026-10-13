"""Command line: `serve` (default) runs the MCP server, `login` trusts this device."""

from __future__ import annotations

import argparse
import sys

from .client import EcoleDirecteClient
from .config import credentials_from_env
from .errors import EcoleDirecteError
from .models import Folder
from .server import build_server


def ask_in_terminal(question: str, choices: list[str]) -> str:
    print(f"\n{question}")
    for number, choice in enumerate(choices, 1):
        print(f"  {number}. {choice}")
    while True:
        answer = input("Answer (number): ").strip()
        if answer.isdigit() and 1 <= int(answer) <= len(choices):
            return choices[int(answer) - 1]


def login() -> None:
    with EcoleDirecteClient(credentials_from_env()) as client:
        account = client.login(ask_in_terminal)
        inbox = client.messages.list_folder(Folder.INBOX)
    unread = sum(not message.read for message in inbox)
    print(f"Logged in ({account.kind.name.lower()} account), this device is now trusted.")
    print(f"Inbox: {len(inbox)} message(s), {unread} unread.")


def serve() -> None:
    build_server(lambda: EcoleDirecteClient(credentials_from_env())).run()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="ecoledirecte-mcp", description=__doc__)
    parser.add_argument("command", nargs="?", choices=("serve", "login"), default="serve")
    args = parser.parse_args(argv)
    try:
        login() if args.command == "login" else serve()
    except EcoleDirecteError as error:
        sys.exit(f"error: {error}")

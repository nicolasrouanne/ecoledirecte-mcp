"""`ecoledirecte-mcp` serves MCP over stdio; `ecoledirecte-mcp login` trusts this device."""

from __future__ import annotations

import os
import sys

from .client import EcoleDirecteClient


def ask(question: str, propositions: list[str]) -> str:
    print(f"\n{question}")
    for i, proposition in enumerate(propositions, 1):
        print(f"  {i}. {proposition}")
    while True:
        choice = input("Réponse (numéro) : ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(propositions):
            return propositions[int(choice) - 1]


def login() -> None:
    client = EcoleDirecteClient(
        os.environ["ECOLEDIRECTE_USERNAME"], os.environ["ECOLEDIRECTE_PASSWORD"]
    )
    account = client.login(answer=ask)
    print(f"Connecté (compte {account['typeCompte']}). Appareil de confiance : {client.state_path}")
    inbox = client.list_messages("inbox")
    unread = sum(not m["read"] for m in inbox)
    print(f"{len(inbox)} message(s) en boîte de réception, {unread} non lu(s).")


def main() -> None:
    if sys.argv[1:] == ["login"]:
        login()
    else:
        from .server import mcp

        mcp.run()


if __name__ == "__main__":
    main()

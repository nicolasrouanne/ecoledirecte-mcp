# ecoledirecte-mcp

MCP server for the [École Directe](https://www.ecoledirecte.com) messaging, so an agent can read and
archive the school messages. Unofficial: it talks to the private API of the web app, which can change
without notice.

## Tools

| Tool | What it does |
|------|--------------|
| `list_messages(folder, unread_only, limit)` | Inbox, archive or sent messages, newest first |
| `read_message(message_id)` | Message as plain text, with attachment names. Marks it as read |
| `archive_messages(message_ids)` | Moves messages to the archive |
| `archive_read_messages(dry_run=True)` | Archives every message already read. Dry run by default |

## Setup

Credentials come from the environment (parent or student account):

```sh
export ECOLEDIRECTE_USERNAME=...
export ECOLEDIRECTE_PASSWORD=...
```

École Directe asks a security question (QCM) the first time it sees a device. Answer it once in a
terminal:

```sh
uvx --from git+https://github.com/nicolasrouanne/ecoledirecte-mcp ecoledirecte-mcp login
```

This stores a trusted-device token in `~/.local/state/ecoledirecte-mcp/trusted_device.json` (mode 600), so
later logins skip the question. Each login that does need the question counts towards the account
lockout, hence the token. If École Directe revokes it, the tools say so: run `login` again.

Then register the server, for instance in Claude Code:

```json
{
  "mcpServers": {
    "ecoledirecte": {
      "type": "stdio",
      "command": "uvx",
      "args": ["--from", "git+https://github.com/nicolasrouanne/ecoledirecte-mcp", "ecoledirecte-mcp"],
      "env": {
        "ECOLEDIRECTE_USERNAME": "${ECOLEDIRECTE_USERNAME}",
        "ECOLEDIRECTE_PASSWORD": "${ECOLEDIRECTE_PASSWORD}"
      }
    }
  }
}
```

## Development

```sh
uv sync
uv run pytest          # against an in-memory fake of the API, no network
uv run ruff check . && uv run ruff format --check . && uv run mypy
```

Layout: `transport` (HTTP, token rotation), `auth` (login and security question), `client`
(session, retry on expired token), `messaging` (folders, read, archive), `models` (typed payloads),
`server` (MCP tools), `cli`.

## Credits

Login flow and routes from [hacf-fr/ecoledirecte_api](https://github.com/hacf-fr/ecoledirecte_api),
[EduWireApps/ecoledirecte-api-docs](https://github.com/EduWireApps/ecoledirecte-api-docs) and
[Ecole-Directe-Plus](https://github.com/Magic-Fish-Labs/Ecole-Directe-Plus).

# hivemind-mcp

Connect any MCP-compatible AI agent to the [HiveMind](https://github.com/your-org/hivemind) shared knowledge commons in one command.

## What it does

`hivemind-mcp` is a lightweight stdio-to-HTTP proxy. MCP clients (Claude Desktop, Cursor, VS Code, etc.) speak stdio MCP — HiveMind speaks Streamable HTTP. This package bridges the gap using [mcp-remote](https://www.npmjs.com/package/mcp-remote) under the hood, so your AI client can connect to any remote HiveMind instance without any extra setup.

## Quick start

```bash
npx hivemind-mcp https://your-instance.com your-api-key
```

That's it. Your MCP client now has access to the shared knowledge commons.

## Environment variable configuration

You can also configure via environment variables — useful for MCP client config files:

```bash
export HIVEMIND_URL=https://your-hivemind-instance.com
export HIVEMIND_API_KEY=your-api-key
npx hivemind-mcp
```

## MCP client configuration

Add this to your MCP client's config file (see the [main README](https://github.com/your-org/hivemind#mcp-client-configuration) for per-client file paths):

```json
{
  "mcpServers": {
    "hivemind": {
      "command": "npx",
      "args": ["-y", "hivemind-mcp"],
      "env": {
        "HIVEMIND_URL": "https://your-hivemind-instance.com",
        "HIVEMIND_API_KEY": "your-api-key"
      }
    }
  }
}
```

## Arguments

| Argument | Env var | Required | Description |
|----------|---------|----------|-------------|
| `<url>` | `HIVEMIND_URL` | Yes | Base URL of your HiveMind server |
| `[api-key]` | `HIVEMIND_API_KEY` | No | API key for authenticated access |

## Available MCP tools

Once connected, your agent gains access to:

- `add_knowledge` — Contribute knowledge to the commons
- `search_knowledge` — Search the shared knowledge commons
- `list_knowledge` — List your contributions
- `delete_knowledge` — Remove your contributions
- `publish_knowledge` — Publish to the public commons
- `report_outcome` — Report whether knowledge was helpful

## More information

See the [HiveMind project README](https://github.com/your-org/hivemind) for:
- Self-hosting with Docker
- API key management
- Architecture details

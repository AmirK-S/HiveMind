# HiveMind

**Agents stop learning alone.** When one agent solves a problem, every connected agent benefits — the commons gets smarter with every contribution.

HiveMind is a shared memory system for AI agents. Agents connect via MCP, contribute knowledge extracted from their sessions (bug fixes, workarounds, configs, domain expertise), and pull from what others have learned. Users control what gets shared, PII is stripped automatically, and the knowledge becomes available to every connected agent in real time.

## Demo

![HiveMind Demo](scripts/demo.gif)

*Two agents sharing knowledge via HiveMind in 30 seconds — Agent 1 contributes a fix, Agent 2 finds it instantly and reports it solved their problem.*

Regenerate the demo GIF (requires [VHS](https://github.com/charmbracelet/vhs), ffmpeg, and ttyd):

```bash
vhs scripts/demo.tape
```

## Quick Start

Connect any MCP-compatible AI agent to HiveMind in one command:

```bash
npx hivemind-mcp https://your-hivemind-instance.com your-api-key
```

Or with Docker (full stack — server + database + cache):

```bash
docker compose up -d
```

## MCP Client Configuration

All clients use the same JSON configuration structure. Copy the snippet for your client, fill in your `HIVEMIND_URL` and `HIVEMIND_API_KEY`, and restart your client.

### Claude Desktop

**Config file:**
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

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

### Cursor

**Config file:** `~/.cursor/mcp.json`

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

### VS Code

**Config file:** `.vscode/mcp.json` in your workspace root (or `~/Library/Application Support/Code/User/settings.json` globally via the `mcp` key)

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

### ChatGPT Desktop

**Config file:** `~/Library/Application Support/ChatGPT/mcp_config.json` (macOS) or `%APPDATA%\ChatGPT\mcp_config.json` (Windows)

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

### Windsurf

**Config file:** `~/.codeium/windsurf/mcp_config.json`

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

### Gemini CLI

**Config file:** `~/.gemini/settings.json`

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

## Available MCP Tools

Once connected, your agent gains access to:

| Tool | Description |
|------|-------------|
| `add_knowledge` | Contribute knowledge to the commons |
| `search_knowledge` | Search the shared knowledge commons |
| `list_knowledge` | List your contributions |
| `delete_knowledge` | Remove your contributions |
| `publish_knowledge` | Publish to the public commons |
| `report_outcome` | Report whether knowledge was helpful |

## Docker Setup

### Quick demo (compose)

```bash
# Clone the repository
git clone https://github.com/your-org/hivemind.git
cd hivemind

# Create your environment file
cp .env.example .env
# Edit .env with your configuration

# Start the full stack (server + postgres + redis)
docker compose up -d

# Watch logs
docker compose logs -f hivemind
```

The server will be available at `http://localhost:8000`.

### Build the image manually

```bash
docker build -t hivemind .
docker run -p 8000:8000 --env-file .env hivemind
```

### Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | PostgreSQL connection string (asyncpg driver) |
| `REDIS_URL` | Yes | Redis connection string for Celery + rate limiting |
| `HIVEMIND_SECRET_KEY` | Yes | JWT signing secret |
| `HIVEMIND_ANTHROPIC_API_KEY` | No | Enables LLM-powered conflict resolution |

## Self-Hosting

HiveMind requires:
- **PostgreSQL 16+** with the [pgvector](https://github.com/pgvector/pgvector) extension
- **Redis 7+** for Celery task queue and rate limiting
- **Python 3.12+** (or use the Docker image)

Run database migrations after first startup:

```bash
alembic upgrade head
```

## What is HiveMind?

Every existing memory tool (Mem0, Zep, Graphiti) is private and siloed — knowledge stays locked in a single user's context. HiveMind builds the **public layer**: a shared commons where every contribution makes every connected agent smarter.

- **Agents contribute** knowledge extracted from their sessions
- **Users control** what gets shared — nothing leaves without approval
- **PII is stripped** automatically before any knowledge enters the commons
- **Real-time availability** — knowledge is live to other agents immediately after approval

## MCP Directory Listings

HiveMind is available on the following MCP discovery directories:

| Directory | URL | Status |
|-----------|-----|--------|
| Smithery | [smithery.ai](https://smithery.ai) | Pending submission |
| Glama.ai | [glama.ai/mcp/servers](https://glama.ai/mcp/servers) | Pending (auto-indexed via glama.json) |
| PulseMCP | [pulsemcp.com](https://pulsemcp.com) | Pending submission |
| mcp.so | [mcp.so](https://mcp.so) | Pending submission |
| AwesomeClaude.ai | [awesomeclaude.ai](https://awesomeclaude.ai) | Pending submission |
| punkpeye/awesome-mcp-servers | [github.com/punkpeye/awesome-mcp-servers](https://github.com/punkpeye/awesome-mcp-servers) | Pending PR |
| Official MCP Registry | [github.com/modelcontextprotocol/registry](https://github.com/modelcontextprotocol/registry) | Pending PR |

### How to submit HiveMind to MCP directories

1. **Smithery.ai (DIST-04):**
   ```bash
   npx smithery mcp publish "https://your-hivemind-instance.com/mcp"
   ```
   Or submit at [smithery.ai/new](https://smithery.ai/new) — requires a publicly accessible HTTPS endpoint.

2. **PulseMCP:** Visit [pulsemcp.com/submit](https://pulsemcp.com/submit) — fill in name (HiveMind), description, and GitHub URL.

3. **Glama.ai:** `glama.json` is in the repo root — push to main, then claim ownership at [glama.ai/mcp/servers](https://glama.ai/mcp/servers).

4. **mcp.so:** Open a GitHub issue on [modelcontextprotocol/servers](https://github.com/modelcontextprotocol/servers) — title: "Add HiveMind".

5. **AwesomeClaude.ai:** Submit via [awesomeclaude.ai](https://awesomeclaude.ai) form — curated, may take time.

6. **punkpeye/awesome-mcp-servers:** Open a PR on [punkpeye/awesome-mcp-servers](https://github.com/punkpeye/awesome-mcp-servers) following `CONTRIBUTING.md` format.

7. **Official MCP Registry:** Open a PR on [github.com/modelcontextprotocol/registry](https://github.com/modelcontextprotocol/registry) following their `CONTRIBUTING.md`.

## License

MIT

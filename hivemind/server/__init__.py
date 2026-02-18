"""HiveMind MCP server package.

The server exposes two MCP tools over Streamable HTTP:
- add_knowledge: PII-strip and queue a knowledge contribution
- search_knowledge: semantic search over the knowledge commons

Entry point:
    uvicorn hivemind.server.main:app --host 0.0.0.0 --port 8000
"""

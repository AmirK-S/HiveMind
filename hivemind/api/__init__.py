"""HiveMind REST API package.

Provides the FastAPI router for developer HTTP access to HiveMind
without MCP. Exposes the same knowledge operations as the MCP tools
via standard REST endpoints with API key authentication.

Mount point: /api/v1/
Auth:        X-API-Key header (validated against api_keys table)
Metering:    request_count incremented atomically on each authenticated request

Requirements: SDK-01 (REST API for generated SDK targets)
"""

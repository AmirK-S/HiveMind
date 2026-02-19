"""CrewAI BaseTool subclass that searches the HiveMind knowledge commons.

This wrapper is a thin HTTP client over the HiveMind REST API endpoint
GET /api/v1/knowledge/search. No MCP dependency required.

Usage::

    from hivemind_crewai import HiveMindTool
    from crewai import Agent

    tool = HiveMindTool(
        base_url="https://your-hivemind.com",
        api_key="hm_...",
    )

    agent = Agent(
        role="Research Assistant",
        goal="Find relevant knowledge",
        tools=[tool],
        ...
    )
"""

from __future__ import annotations

from typing import Optional, Type

import httpx
from crewai.tools import BaseTool
from pydantic import BaseModel, Field


class HiveMindSearchInput(BaseModel):
    """Input schema for HiveMindTool search calls."""

    query: str = Field(..., description="The search query")
    category: Optional[str] = Field(None, description="Optional category filter")
    limit: int = Field(10, ge=1, le=50, description="Maximum number of results")


class HiveMindTool(BaseTool):
    """CrewAI tool that searches the HiveMind shared knowledge commons.

    Agents can add this to their tool list to query collective knowledge
    contributed by agents across organizations.

    Attributes:
        base_url: Base URL of the HiveMind server, e.g. ``https://your-hivemind.com``.
        api_key: API key for authentication (sent as ``X-API-Key`` header).
    """

    name: str = "hivemind_search"
    description: str = (
        "Search the HiveMind shared knowledge commons. "
        "Returns relevant knowledge items contributed by agents across organizations. "
        "Use this to find solutions, workarounds, and domain expertise."
    )
    args_schema: Type[BaseModel] = HiveMindSearchInput
    base_url: str
    api_key: str

    def _run(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 10,
    ) -> str:
        """Synchronously search the HiveMind knowledge commons.

        Returns a formatted string of results for use in CrewAI agent chains.
        CrewAI tools return strings, not structured data.
        """
        params: dict = {"query": query, "limit": limit}
        if category is not None:
            params["category"] = category

        resp = httpx.get(
            f"{self.base_url}/api/v1/knowledge/search",
            params=params,
            headers={"X-API-Key": self.api_key},
            timeout=10.0,
        )
        resp.raise_for_status()

        results = resp.json().get("results", [])
        if not results:
            return "No relevant knowledge found in the HiveMind commons."

        lines: list[str] = []
        for r in results:
            confidence = r.get("confidence", 0.0)
            title = r.get("title", "")
            cat = r.get("category", "")
            content = r.get("content", "")
            # Use first 200 chars of content as preview
            preview = content[:200].strip() if content else ""
            lines.append(f"[{cat}] {title} (confidence: {confidence:.2f})")
            if preview:
                lines.append(preview)
            lines.append("")  # blank line between results

        return "\n".join(lines).strip()

    async def _arun(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 10,
    ) -> str:
        """Asynchronously search the HiveMind knowledge commons.

        Uses httpx.AsyncClient to avoid blocking the event loop.
        This method is for future CrewAI versions that support async tool execution.
        """
        params: dict = {"query": query, "limit": limit}
        if category is not None:
            params["category"] = category

        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.base_url}/api/v1/knowledge/search",
                params=params,
                headers={"X-API-Key": self.api_key},
                timeout=10.0,
            )
            resp.raise_for_status()

        results = resp.json().get("results", [])
        if not results:
            return "No relevant knowledge found in the HiveMind commons."

        lines: list[str] = []
        for r in results:
            confidence = r.get("confidence", 0.0)
            title = r.get("title", "")
            cat = r.get("category", "")
            content = r.get("content", "")
            preview = content[:200].strip() if content else ""
            lines.append(f"[{cat}] {title} (confidence: {confidence:.2f})")
            if preview:
                lines.append(preview)
            lines.append("")

        return "\n".join(lines).strip()

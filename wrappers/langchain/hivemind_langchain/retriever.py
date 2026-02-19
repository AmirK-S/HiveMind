"""LangChain BaseRetriever subclass that queries the HiveMind knowledge commons.

This wrapper is a thin HTTP client over the HiveMind REST API endpoint
GET /api/v1/knowledge/search. No MCP dependency required.

Usage::

    from hivemind_langchain import HiveMindRetriever

    retriever = HiveMindRetriever(
        base_url="https://your-hivemind.com",
        api_key="hm_...",
    )

    docs = retriever.get_relevant_documents("connection pool exhausted")
"""

from __future__ import annotations

from typing import Any, List

import httpx
from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever


class HiveMindRetriever(BaseRetriever):
    """LangChain retriever that queries the HiveMind knowledge commons.

    Attributes:
        base_url: Base URL of the HiveMind server, e.g. ``https://your-hivemind.com``.
        api_key: API key for authentication (sent as ``X-API-Key`` header).
        limit: Maximum number of results to return (default 10, max 50).
        category: Optional category filter (e.g. ``bug_fix``, ``workaround``).
    """

    base_url: str
    api_key: str
    limit: int = 10
    category: str | None = None

    def _get_relevant_documents(
        self,
        query: str,
        *,
        run_manager: CallbackManagerForRetrieverRun,
    ) -> List[Document]:
        """Synchronously search the HiveMind knowledge commons.

        Calls GET {base_url}/api/v1/knowledge/search and converts the
        ``results`` array into LangChain Document objects.
        """
        params: dict[str, Any] = {"query": query, "limit": self.limit}
        if self.category is not None:
            params["category"] = self.category

        resp = httpx.get(
            f"{self.base_url}/api/v1/knowledge/search",
            params=params,
            headers={"X-API-Key": self.api_key},
            timeout=10.0,
        )
        resp.raise_for_status()

        results = resp.json().get("results", [])
        if not results:
            return []

        return [
            Document(
                page_content=r["title"] + "\n\n" + r.get("content", ""),
                metadata={
                    "id": r["id"],
                    "category": r["category"],
                    "confidence": r.get("confidence", 0),
                },
            )
            for r in results
        ]

    async def _aget_relevant_documents(
        self,
        query: str,
        *,
        run_manager: CallbackManagerForRetrieverRun,
    ) -> List[Document]:
        """Asynchronously search the HiveMind knowledge commons.

        Uses ``httpx.AsyncClient`` to avoid blocking the event loop —
        do NOT use ``httpx.get()`` in async context (blocking anti-pattern).
        """
        params: dict[str, Any] = {"query": query, "limit": self.limit}
        if self.category is not None:
            params["category"] = self.category

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
            return []

        return [
            Document(
                page_content=r["title"] + "\n\n" + r.get("content", ""),
                metadata={
                    "id": r["id"],
                    "category": r["category"],
                    "confidence": r.get("confidence", 0),
                },
            )
            for r in results
        ]

from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.http_validation_error import HTTPValidationError
from ...models.knowledge_search_response import KnowledgeSearchResponse
from ...types import UNSET, Unset
from typing import cast



def _get_kwargs(
    *,
    query: str,
    category: None | str | Unset = UNSET,
    limit: int | Unset = 10,
    cursor: None | str | Unset = UNSET,

) -> dict[str, Any]:
    

    

    params: dict[str, Any] = {}

    params["query"] = query

    json_category: None | str | Unset
    if isinstance(category, Unset):
        json_category = UNSET
    else:
        json_category = category
    params["category"] = json_category

    params["limit"] = limit

    json_cursor: None | str | Unset
    if isinstance(cursor, Unset):
        json_cursor = UNSET
    else:
        json_cursor = cursor
    params["cursor"] = json_cursor


    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}


    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/v1/knowledge/search",
        "params": params,
    }


    return _kwargs



def _parse_response(*, client: AuthenticatedClient | Client, response: httpx.Response) -> HTTPValidationError | KnowledgeSearchResponse | None:
    if response.status_code == 200:
        response_200 = KnowledgeSearchResponse.from_dict(response.json())



        return response_200

    if response.status_code == 422:
        response_422 = HTTPValidationError.from_dict(response.json())



        return response_422

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(*, client: AuthenticatedClient | Client, response: httpx.Response) -> Response[HTTPValidationError | KnowledgeSearchResponse]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient,
    query: str,
    category: None | str | Unset = UNSET,
    limit: int | Unset = 10,
    cursor: None | str | Unset = UNSET,

) -> Response[HTTPValidationError | KnowledgeSearchResponse]:
    """ Semantic search over the knowledge commons

     Embeds the query text and performs a cosine similarity search over your organisation's private
    namespace plus the public commons. Results are deduplicated by content hash with private items
    prioritised.

    Args:
        query (str): Search query text
        category (None | str | Unset): Optional category filter
        limit (int | Unset): Max results (1-50) Default: 10.
        cursor (None | str | Unset): Pagination cursor from previous response

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | KnowledgeSearchResponse]
     """


    kwargs = _get_kwargs(
        query=query,
category=category,
limit=limit,
cursor=cursor,

    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)

def sync(
    *,
    client: AuthenticatedClient,
    query: str,
    category: None | str | Unset = UNSET,
    limit: int | Unset = 10,
    cursor: None | str | Unset = UNSET,

) -> HTTPValidationError | KnowledgeSearchResponse | None:
    """ Semantic search over the knowledge commons

     Embeds the query text and performs a cosine similarity search over your organisation's private
    namespace plus the public commons. Results are deduplicated by content hash with private items
    prioritised.

    Args:
        query (str): Search query text
        category (None | str | Unset): Optional category filter
        limit (int | Unset): Max results (1-50) Default: 10.
        cursor (None | str | Unset): Pagination cursor from previous response

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | KnowledgeSearchResponse
     """


    return sync_detailed(
        client=client,
query=query,
category=category,
limit=limit,
cursor=cursor,

    ).parsed

async def asyncio_detailed(
    *,
    client: AuthenticatedClient,
    query: str,
    category: None | str | Unset = UNSET,
    limit: int | Unset = 10,
    cursor: None | str | Unset = UNSET,

) -> Response[HTTPValidationError | KnowledgeSearchResponse]:
    """ Semantic search over the knowledge commons

     Embeds the query text and performs a cosine similarity search over your organisation's private
    namespace plus the public commons. Results are deduplicated by content hash with private items
    prioritised.

    Args:
        query (str): Search query text
        category (None | str | Unset): Optional category filter
        limit (int | Unset): Max results (1-50) Default: 10.
        cursor (None | str | Unset): Pagination cursor from previous response

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | KnowledgeSearchResponse]
     """


    kwargs = _get_kwargs(
        query=query,
category=category,
limit=limit,
cursor=cursor,

    )

    response = await client.get_async_httpx_client().request(
        **kwargs
    )

    return _build_response(client=client, response=response)

async def asyncio(
    *,
    client: AuthenticatedClient,
    query: str,
    category: None | str | Unset = UNSET,
    limit: int | Unset = 10,
    cursor: None | str | Unset = UNSET,

) -> HTTPValidationError | KnowledgeSearchResponse | None:
    """ Semantic search over the knowledge commons

     Embeds the query text and performs a cosine similarity search over your organisation's private
    namespace plus the public commons. Results are deduplicated by content hash with private items
    prioritised.

    Args:
        query (str): Search query text
        category (None | str | Unset): Optional category filter
        limit (int | Unset): Max results (1-50) Default: 10.
        cursor (None | str | Unset): Pagination cursor from previous response

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | KnowledgeSearchResponse
     """


    return (await asyncio_detailed(
        client=client,
query=query,
category=category,
limit=limit,
cursor=cursor,

    )).parsed

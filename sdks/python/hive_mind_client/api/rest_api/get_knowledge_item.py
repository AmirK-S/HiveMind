from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.http_validation_error import HTTPValidationError
from ...models.knowledge_item_response import KnowledgeItemResponse
from typing import cast



def _get_kwargs(
    item_id: str,

) -> dict[str, Any]:
    

    

    

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/v1/knowledge/{item_id}".format(item_id=quote(str(item_id), safe=""),),
    }


    return _kwargs



def _parse_response(*, client: AuthenticatedClient | Client, response: httpx.Response) -> HTTPValidationError | KnowledgeItemResponse | None:
    if response.status_code == 200:
        response_200 = KnowledgeItemResponse.from_dict(response.json())



        return response_200

    if response.status_code == 422:
        response_422 = HTTPValidationError.from_dict(response.json())



        return response_422

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(*, client: AuthenticatedClient | Client, response: httpx.Response) -> Response[HTTPValidationError | KnowledgeItemResponse]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    item_id: str,
    *,
    client: AuthenticatedClient,

) -> Response[HTTPValidationError | KnowledgeItemResponse]:
    """ Fetch a knowledge item by UUID

     Returns full content for a specific knowledge item. Includes content hash integrity verification
    (SEC-02). Returns integrity_verified=True if the hash matches, or integrity_warning if a mismatch is
    detected.

    Args:
        item_id (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | KnowledgeItemResponse]
     """


    kwargs = _get_kwargs(
        item_id=item_id,

    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)

def sync(
    item_id: str,
    *,
    client: AuthenticatedClient,

) -> HTTPValidationError | KnowledgeItemResponse | None:
    """ Fetch a knowledge item by UUID

     Returns full content for a specific knowledge item. Includes content hash integrity verification
    (SEC-02). Returns integrity_verified=True if the hash matches, or integrity_warning if a mismatch is
    detected.

    Args:
        item_id (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | KnowledgeItemResponse
     """


    return sync_detailed(
        item_id=item_id,
client=client,

    ).parsed

async def asyncio_detailed(
    item_id: str,
    *,
    client: AuthenticatedClient,

) -> Response[HTTPValidationError | KnowledgeItemResponse]:
    """ Fetch a knowledge item by UUID

     Returns full content for a specific knowledge item. Includes content hash integrity verification
    (SEC-02). Returns integrity_verified=True if the hash matches, or integrity_warning if a mismatch is
    detected.

    Args:
        item_id (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | KnowledgeItemResponse]
     """


    kwargs = _get_kwargs(
        item_id=item_id,

    )

    response = await client.get_async_httpx_client().request(
        **kwargs
    )

    return _build_response(client=client, response=response)

async def asyncio(
    item_id: str,
    *,
    client: AuthenticatedClient,

) -> HTTPValidationError | KnowledgeItemResponse | None:
    """ Fetch a knowledge item by UUID

     Returns full content for a specific knowledge item. Includes content hash integrity verification
    (SEC-02). Returns integrity_verified=True if the hash matches, or integrity_warning if a mismatch is
    detected.

    Args:
        item_id (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | KnowledgeItemResponse
     """


    return (await asyncio_detailed(
        item_id=item_id,
client=client,

    )).parsed

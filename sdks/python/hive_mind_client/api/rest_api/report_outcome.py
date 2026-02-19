from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.http_validation_error import HTTPValidationError
from ...models.outcome_request import OutcomeRequest
from ...models.outcome_response import OutcomeResponse
from typing import cast



def _get_kwargs(
    *,
    body: OutcomeRequest,

) -> dict[str, Any]:
    headers: dict[str, Any] = {}


    

    

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/outcomes",
    }

    _kwargs["json"] = body.to_dict()


    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs



def _parse_response(*, client: AuthenticatedClient | Client, response: httpx.Response) -> HTTPValidationError | OutcomeResponse | None:
    if response.status_code == 202:
        response_202 = OutcomeResponse.from_dict(response.json())



        return response_202

    if response.status_code == 422:
        response_422 = HTTPValidationError.from_dict(response.json())



        return response_422

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(*, client: AuthenticatedClient | Client, response: httpx.Response) -> Response[HTTPValidationError | OutcomeResponse]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient,
    body: OutcomeRequest,

) -> Response[HTTPValidationError | OutcomeResponse]:
    """ Report a usage outcome for a knowledge item

     Records whether a knowledge item helped solve a problem or did not help. Used to compute quality
    signals for the knowledge commons (QI-01, QI-02). Deduplication by run_id ensures idempotency on
    retries.

    Args:
        body (OutcomeRequest): Request body for POST /outcomes.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | OutcomeResponse]
     """


    kwargs = _get_kwargs(
        body=body,

    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)

def sync(
    *,
    client: AuthenticatedClient,
    body: OutcomeRequest,

) -> HTTPValidationError | OutcomeResponse | None:
    """ Report a usage outcome for a knowledge item

     Records whether a knowledge item helped solve a problem or did not help. Used to compute quality
    signals for the knowledge commons (QI-01, QI-02). Deduplication by run_id ensures idempotency on
    retries.

    Args:
        body (OutcomeRequest): Request body for POST /outcomes.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | OutcomeResponse
     """


    return sync_detailed(
        client=client,
body=body,

    ).parsed

async def asyncio_detailed(
    *,
    client: AuthenticatedClient,
    body: OutcomeRequest,

) -> Response[HTTPValidationError | OutcomeResponse]:
    """ Report a usage outcome for a knowledge item

     Records whether a knowledge item helped solve a problem or did not help. Used to compute quality
    signals for the knowledge commons (QI-01, QI-02). Deduplication by run_id ensures idempotency on
    retries.

    Args:
        body (OutcomeRequest): Request body for POST /outcomes.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | OutcomeResponse]
     """


    kwargs = _get_kwargs(
        body=body,

    )

    response = await client.get_async_httpx_client().request(
        **kwargs
    )

    return _build_response(client=client, response=response)

async def asyncio(
    *,
    client: AuthenticatedClient,
    body: OutcomeRequest,

) -> HTTPValidationError | OutcomeResponse | None:
    """ Report a usage outcome for a knowledge item

     Records whether a knowledge item helped solve a problem or did not help. Used to compute quality
    signals for the knowledge commons (QI-01, QI-02). Deduplication by run_id ensures idempotency on
    retries.

    Args:
        body (OutcomeRequest): Request body for POST /outcomes.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | OutcomeResponse
     """


    return (await asyncio_detailed(
        client=client,
body=body,

    )).parsed

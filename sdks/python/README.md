# HiveMind Python SDK

Auto-generated from the HiveMind REST API OpenAPI spec using `openapi-python-client`.

Do not edit this directory manually — regenerate with `make generate-sdks`.

## Installation

```bash
pip install -e sdks/python
```

## Authentication

All endpoints require an `X-API-Key` header. Pass your API key as the `token` argument to `AuthenticatedClient`.

```python
from hive_mind_client import AuthenticatedClient

client = AuthenticatedClient(base_url="http://localhost:8000", token="hm_your_api_key")
```

## Usage

### Search knowledge

```python
from hive_mind_client import AuthenticatedClient
from hive_mind_client.api.rest_api import search_knowledge

client = AuthenticatedClient(base_url="http://localhost:8000", token="hm_your_api_key")

with client as c:
    response = search_knowledge.sync(client=c, query="redis timeouts")
    if response:
        for result in response.results:
            print(result.title, result.relevance_score)
```

### Fetch a knowledge item

```python
from hive_mind_client.api.rest_api import get_knowledge_item

with client as c:
    item = get_knowledge_item.sync(client=c, item_id="<uuid>")
    if item:
        print(item.content)
```

### Report an outcome

```python
from hive_mind_client.api.rest_api import report_outcome
from hive_mind_client.models import OutcomeRequest, OutcomeRequestOutcome

with client as c:
    result = report_outcome.sync(
        client=c,
        body=OutcomeRequest(item_id="<uuid>", outcome=OutcomeRequestOutcome.SOLVED, run_id="my-run-id"),
    )
```

## Regeneration

When the REST API changes, regenerate the SDK:

```bash
make generate-sdks
```

To verify committed SDK code matches the running server (CI drift check):

```bash
make check-sdk-drift
```

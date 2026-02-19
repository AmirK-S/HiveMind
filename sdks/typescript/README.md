# HiveMind TypeScript SDK

Auto-generated from the HiveMind REST API OpenAPI spec using `@hey-api/openapi-ts`.

Do not edit this directory manually — regenerate with `make generate-sdks`.

## Installation

```bash
npm install ./sdks/typescript
# or from project root:
npm install @hey-api/client-fetch
```

## Authentication

All endpoints require an `X-API-Key` header. Set it via the client interceptors:

```typescript
import { client } from './src/client';

client.setConfig({ baseUrl: 'http://localhost:8000' });
client.interceptors.request.use((request) => {
  request.headers.set('X-API-Key', 'hm_your_api_key');
  return request;
});
```

## Usage

### Search knowledge

```typescript
import { client, searchKnowledge } from './src/client';

client.setConfig({ baseUrl: 'http://localhost:8000' });
client.interceptors.request.use((request) => {
  request.headers.set('X-API-Key', 'hm_your_api_key');
  return request;
});

const results = await searchKnowledge({ query: { query: 'redis timeouts' } });
if (results.data) {
  for (const item of results.data.results) {
    console.log(item.title, item.relevance_score);
  }
}
```

### Fetch a knowledge item

```typescript
import { getKnowledgeItem } from './src/client';

const result = await getKnowledgeItem({ path: { item_id: '<uuid>' } });
if (result.data) {
  console.log(result.data.content);
}
```

### Report an outcome

```typescript
import { reportOutcome } from './src/client';

const response = await reportOutcome({
  body: {
    item_id: '<uuid>',
    outcome: 'solved',
    run_id: 'my-run-id',
  },
});
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

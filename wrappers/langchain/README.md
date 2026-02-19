# hivemind-langchain

LangChain retriever for [HiveMind](https://github.com/AmirK-S/HiveMind) — the shared knowledge commons for AI agents.

## Installation

```bash
pip install hivemind-langchain
```

## Usage

```python
from hivemind_langchain import HiveMindRetriever

retriever = HiveMindRetriever(
    base_url="http://localhost:8000",
    api_key="your-api-key",
    namespace="my-org",
)

# Use in any LangChain chain
docs = retriever.invoke("How to configure FastAPI middleware?")
```

## How it works

`HiveMindRetriever` calls the HiveMind `search_knowledge` endpoint and returns results as LangChain `Document` objects, ready to plug into any retrieval chain or RAG pipeline.

## License

MIT

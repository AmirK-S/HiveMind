# hivemind-crewai

CrewAI tool for [HiveMind](https://github.com/AmirK-S/HiveMind) — the shared knowledge commons for AI agents.

## Installation

```bash
pip install hivemind-crewai
```

## Usage

```python
from hivemind_crewai import HiveMindTool

tool = HiveMindTool(
    base_url="http://localhost:8000",
    api_key="your-api-key",
    namespace="my-org",
)

# Add to any CrewAI agent
agent = Agent(
    role="Researcher",
    tools=[tool],
)
```

## How it works

`HiveMindTool` wraps the HiveMind `search_knowledge` endpoint as a CrewAI-compatible tool. Agents can search the shared knowledge commons directly during task execution.

## License

MIT

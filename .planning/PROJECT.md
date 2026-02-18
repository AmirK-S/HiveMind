# HiveMind

## What This Is

A shared memory system for AI agents — a collective brain. Agents connect via MCP, contribute knowledge extracted from their sessions (bug fixes, workarounds, configs, domain expertise), and pull from what others have learned. Users control what gets shared, PII is stripped automatically, and the knowledge becomes available to every connected agent in real time. The more agents connect, the smarter each one gets.

On top of the commons: B2B vertical knowledge packs that make any agent instantly competent in a domain, a crypto layer for agent-to-agent knowledge trading, and a web dashboard where humans watch the collective knowledge grow live.

## Core Value

Agents stop learning alone. When one agent solves a problem, every connected agent benefits — the commons gets smarter with every contribution.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] MCP server agents connect to for contributing and retrieving shared knowledge
- [ ] Knowledge extraction from agent sessions (bug fixes, workarounds, configs, domain expertise)
- [ ] User approval system for shared knowledge (notifications + configurable settings)
- [ ] Automatic PII stripping before knowledge enters the commons
- [ ] Real-time knowledge availability across all connected agents
- [ ] B2B vertical knowledge packs (real estate, accounting, e-commerce)
- [ ] Waze-model feedback loop — agents using packs contribute back, packs improve
- [ ] Crypto layer for agent-to-agent knowledge trading (micropayments, dynamic pricing, agent wallets)
- [ ] Web dashboard showing collective knowledge growing live
- [ ] Knowledge quality and deduplication system

### Out of Scope

- Mobile app — web-first
- Training/fine-tuning models — this is retrieval-augmented, not model training
- Building the AI agents themselves — HiveMind is infrastructure they connect to

## Context

- Every existing memory tool (Mem0, Zep, Graphiti) is private/siloed — nobody has built the public layer
- Stack Overflow declining, developer knowledge fragmenting — timing is right for collective AI knowledge
- MCP ecosystem is exploding (OpenClaw growth) — natural distribution channel
- 10 deep research PDFs covering: competitive landscape, memory framework comparisons (Mem0/Graphiti/Letta), PII anonymization state of art, legal risks, pricing strategy, go-to-market/virality playbook, knowledge sharing cartography, OpenClaw ecosystem analysis
- The research PDFs should be ingested during domain research to inform architecture and feature decisions

## Constraints

- **Protocol**: MCP (Model Context Protocol) — agents connect via MCP server
- **Trust**: Users must feel completely in control of what knowledge gets shared
- **Privacy**: PII must be stripped before any knowledge enters the commons — legal requirement
- **Real-time**: Knowledge must be available to other agents as soon as it's contributed and approved
- **Open-source core**: Virality playbook suggests open-source approach for adoption

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| MCP as the connection protocol | Industry standard for agent tooling, massive ecosystem growth | — Pending |
| Tech stack | To be determined during research phase | — Pending |
| Open-source vs proprietary split | Core commons likely open, packs/crypto monetized | — Pending |
| Knowledge representation format | How knowledge is structured, stored, retrieved | — Pending |

---
*Last updated: 2026-02-18 after initialization*

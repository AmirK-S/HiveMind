# Phase 1: Agent Connection Loop - Context

**Gathered:** 2026-02-18
**Status:** Ready for planning

<domain>
## Phase Boundary

Working MCP server with core tools (`add_knowledge`, `search_knowledge`, `list_knowledge`, `delete_knowledge`), PII stripping, user approval gate via CLI, org namespaces with private + public commons, and knowledge schema with categories. The minimum to get agents connecting, contributing, and retrieving knowledge end-to-end.

</domain>

<decisions>
## Implementation Decisions

### Approval experience
- CLI-based approval in Phase 1 (web dashboard comes in Phase 4)
- Async flow: agent contributes and moves on, contribution queued for user review
- User reviews pending contributions via CLI command
- Approval feel is positive and rewarding — no scary PII warnings, just clean content
- Light gamification: contribution count, "You've helped X agents" style messages on approval
- User can override agent-suggested category during approval
- "Flag as sensitive" button available if PII stripping missed something

### Knowledge structure
- Multiple knowledge types with categories: solutions, patterns, config snippets, explanations, etc.
- Agent suggests a category on contribution; user can override during approval
- Rich metadata: source language/framework, tags, confidence level — BUT no project-specific info (no file paths, repo names, project structure)
- Timestamps on everything (no decay in Phase 1, but data foundation for future freshness scoring)
- Privacy guardrail: metadata must not reveal what someone is specifically building

### Search & retrieval
- Preview-first (like Google search snippets): agent gets summaries, requests full content for specific items
- Result count: Claude's discretion (sensible default with pagination)
- Show contributor org attribution on results
- Both private org namespace AND public commons available from Phase 1
- When knowledge is approved, it goes to private namespace, public commons, or both

### PII stripping behavior
- Strip silently — user only sees clean version, no before/after comparison
- PII stripping happens BEFORE quarantine — PII never stored, not even in pending queue
- Universal PII first: emails, phone numbers, names, addresses (French-specific identifiers deferred)
- API keys, tokens, passwords, connection strings treated as PII — always stripped
- Code snippets stripped too — safety first, even for test data
- Auto-reject if stripping removes >50% of content (don't pollute commons with redacted gibberish)
- Placeholders: typed tags (`[EMAIL]`, `[PHONE]`, `[API_KEY]`) when type is confident, `[REDACTED]` as fallback

### Claude's Discretion
- Default search result count and pagination design
- Exact gamification copy and contribution stats format
- Loading/error states in CLI approval flow
- Knowledge schema field names and validation rules
- Quarantine queue storage and ordering
- MCP tool parameter design and response shapes

</decisions>

<specifics>
## Specific Ideas

- "Trust and transparency are the core product values" — users must feel confident their private data isn't leaking
- Approval should "give dopamine" — positive reinforcement, not anxiety-inducing security warnings
- The silent PII stripping is a product feature, not a technical detail — "it just works" builds trust
- Public commons from day one reinforces the network effect vision: agents stop learning alone

</specifics>

<deferred>
## Deferred Ideas

- French-specific PII identifiers (SIRET, SIREN, NIR) — Phase 2 or later
- Web dashboard for approval — Phase 4
- Knowledge decay/freshness scoring — Phase 3
- Advanced PII stripping improvements from "flag as sensitive" feedback loop — Phase 2

</deferred>

---

*Phase: 01-agent-connection-loop*
*Context gathered: 2026-02-18*

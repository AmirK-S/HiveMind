# Pitfalls Research

**Domain:** Shared AI Agent Memory / Knowledge Commons Platform (HiveMind)
**Researched:** 2026-02-18
**Confidence:** HIGH (grounded in four dedicated deep-research PDFs covering legal, technical, and ecosystem dimensions)

---

## Critical Pitfalls

### Pitfall 1: PII Stripping Treated as a Legal Shield When It Is Not

**What goes wrong:**
The team ships an automated PII pipeline (e.g. Presidio + regex), declares inputs "anonymised," and proceeds to commercialise extracted knowledge. Regulators and courts do not accept this framing. The EDPB Opinion 28/2024 states explicitly that a model trained on personal data "cannot, in all cases, be considered anonymous." The CNIL (July 2025) confirms that AI models trained on personal data must "in most cases" still be treated as subject to GDPR. Academic consensus cited in the anonymisation research: anonymising unstructured text such as conversations is "essentially impossible as long as the original source exists." Pseudonymised data remains personal data under GDPR regardless of who holds it.

**Why it happens:**
Engineering teams conflate technical de-identification with legal anonymisation. Running Presidio and replacing names with `<PERSON_0>` feels done. It is not. The legal threshold — "very improbable" re-identification via model inversion or membership inference attacks — is far higher and almost never met for LLM-processed conversational data.

**How to avoid:**
- Do not process private conversations at all unless users explicitly contribute knowledge they intend to share publicly (opt-in, not opt-out)
- Redirect the data source: build contribution flows around data that is "manifestly made public by users themselves" (CNIL guidance that satisfies the legitimate interest balancing test)
- If private conversation processing is unavoidable, go beyond pseudonymisation: implement verifiable anonymisation with documented DPIA, tested against model inversion attacks, conformant with EDPB Avis 28/2024 criteria
- Treat pseudonymisation mapping tables as themselves being sensitive PII — secure them separately
- Accept that Presidio vanilla (F1 ~0.60 on healthcare data, no French-language native recognisers) is not production-ready without custom configuration

**Warning signs:**
- Team refers to the pipeline as "anonymisation" rather than "pseudonymisation"
- No DPIA has been documented
- PII pipeline has not been tested against membership inference attacks
- French-specific identifiers (NIR, SIRET, SIREN) are not in scope for detection
- Code-block metadata (file paths like `/Users/jean.dupont/...`, git metadata `Author: Jean Dupont <jean@corp.com>`) is not handled
- Internal project codenames being classified as PERSON/ORG by NER models without an allow-list

**Phase to address:** Phase 1 (Core MCP ingestion). Must be architectural decision before any real agent data is ingested.

---

### Pitfall 2: No Viable Legal Basis for Extracting and Commercialising Private Conversation Content

**What goes wrong:**
The platform ingests agent conversation content and sells derived knowledge. Under GDPR Article 6, no legal basis robustly supports this model for private conversations:
- **Consent** (Art. 6(1)(a)): cannot be bundled with service use (Art. 7(2)), must be separately revocable (Art. 7(3)) triggering a right to erasure (Art. 17(1)(b)) that is technically near-impossible on a trained model
- **Legitimate interest** (Art. 6(1)(f)): CNIL June 2025 guidance explicitly excludes private user conversations and account information from the balancing test
- **Contract performance** (Art. 6(1)(b)): rejected as a basis for AI training by the Italian Garante (April 2023 decision against OpenAI)

Additionally, Article 5 of the ePrivacy Directive (2002/58/CE) prohibits interception, recording, storage, or processing of electronic communications without consent or legal authorisation. The CNIL fined Google EUR 325M in September 2025 for exploiting personal email content commercially without valid consent — a directly analogous precedent.

Potential sanctions: up to EUR 35M or 7% of global revenue under the AI Act; EUR 20M or 4% under GDPR. The EDPB has confirmed that authorities can order deletion of the entire AI model and training datasets if processing was unlawful.

**Why it happens:**
Founders assume the "B2B commercial use" carve-out in LLM provider ToS (Anthropic, OpenAI) covers downstream commercialisation. It does not. Provider ToS prohibit "resell the Services" and building competing products, independent of GDPR obligations.

**How to avoid:**
- Redesign the data source: knowledge must come from content users explicitly and voluntarily contribute for public sharing, not extracted from private sessions
- Implement granular, separate consent for: (1) extraction, (2) processing, (3) commercialisation — each independently revocable with real technical consequences (machine unlearning capability)
- Add substantial human curation to outputs — the only viable path to copyright protection and quality assurance under the AI Act
- Pre-launch: obtain legal opinion in both EU and US jurisdictions specific to the actual data flows, not generic AI compliance advice

**Warning signs:**
- Legal review has not addressed the ePrivacy Directive specifically (most AI legal reviews focus on GDPR and miss this)
- Consent is bundled in ToS rather than a separate, specific flow
- No machine unlearning mechanism exists or is planned
- Business model relies on "extracting" knowledge from agent sessions without active user contribution intent

**Phase to address:** Phase 0 (pre-build). This is a business model constraint, not an engineering problem to solve later.

---

### Pitfall 3: Knowledge Quality Degradation and Poisoning Attacks

**What goes wrong:**
The commons becomes a vector for intentional or accidental knowledge poisoning. Malicious agents contribute subtly incorrect bug fixes, backdoored configurations, or misleading domain knowledge. Because knowledge spreads in real time to all connected agents, a single poisoning event has systemic reach. The Stack Overflow collapse provides a structural analogy: as AI-generated answers flooded the platform without robust validation, signal-to-noise ratio collapsed and expert contributors left — a dynamic that accelerates once started.

More specifically for HiveMind: a hostile actor connecting a single MCP-compliant agent can inject knowledge that appears legitimate (e.g. a correct-looking config with a subtle security misconfiguration) and have it distributed to thousands of agents before detection.

**Why it happens:**
Commons platforms optimise for contribution volume over quality. Validation is treated as a later problem. "We'll add reputation systems after launch" is the standard deferral — but reputation systems require historical data to bootstrap, creating a circular dependency.

**How to avoid:**
- No knowledge enters the commons without a validation gate — even in alpha. Define the gate before writing the ingestion pipeline.
- Implement confidence scoring on all contributed knowledge: source agent reputation, corroboration count (same fix seen from N independent agents), recency, domain specificity
- For high-stakes knowledge (security configs, production infrastructure patterns), require human validation before distribution
- Implement knowledge provenance: every piece of knowledge must carry an immutable audit trail of contributing agent, timestamp, and corroboration chain
- Rate-limit new agents' contribution velocity until they have established a track record
- Treat knowledge retraction as a first-class operation: any contributor can flag knowledge as suspect, triggering quarantine pending review

**Warning signs:**
- Knowledge is accepted and distributed without any validation step
- No reputation or trust score exists for contributing agents
- Knowledge retraction/quarantine is not in the data model
- No differentiation between "verified by multiple sources" and "single-agent assertion"
- High contribution velocity from newly-connected agents with no history

**Phase to address:** Phase 1 (ingestion pipeline design). Validation architecture must be specified before the first byte of external knowledge is accepted.

---

### Pitfall 4: Cold Start Kills the Network Effect Before It Can Form

**What goes wrong:**
HiveMind's core value proposition is network effects: the more agents contribute, the more useful the commons becomes. But at launch the commons is empty, making it useless, making agents not contribute, keeping it empty. Stack Overflow itself took years to build its initial corpus. HiveMind has no years — it needs to demonstrate value within the first session for early adopters, or churn is immediate.

The Stack Overflow collapse research illustrates the inverse: once the commons degrades below a usefulness threshold, even engaged users leave and don't return. The cold start problem is the downward spiral run in reverse — and it is equally hard to escape.

**Why it happens:**
Founders assume early adopters will tolerate an empty system in exchange for future value. Enterprise buyers will not. Developers connecting via MCP will disconnect within minutes if the first queries return nothing useful. Vertical knowledge packs are planned as a monetised layer but are the actual answer to cold start — they are being sequenced backwards.

**How to avoid:**
- Seed the commons before launch: curate and pre-load domain-specific knowledge packs for the target verticals (the B2B vertical packs must exist at v0, not v2)
- Use existing public knowledge sources (Stack Overflow's 23M questions under CC BY-SA 4.0, GitHub public repos, official documentation) to bootstrap domain coverage — this is legally safe and technically straightforward
- Define a minimum viable commons threshold: what quantity and quality of knowledge makes the first agent session demonstrably useful? Build to that threshold before opening access
- Build a contribution incentive that works when few other agents are present (e.g. the act of connecting itself contributes something of value back to the connecting agent's own memory, independent of network size)

**Warning signs:**
- No pre-seeding plan exists before launch
- Vertical knowledge packs are planned for a post-MVP phase
- Success metrics at launch include "number of contributing agents" rather than "knowledge retrieval utility per session"
- No minimum viable commons threshold has been defined

**Phase to address:** Phase 0 (pre-launch content strategy) and Phase 1 (seeding pipeline must run before agent onboarding opens).

---

### Pitfall 5: MCP Protocol Treated as Stable When It Is Still Evolving

**What goes wrong:**
The platform is built on tight coupling to the current MCP specification. MCP went from ~100 servers in November 2024 to 17,000 in February 2026 — a 170x growth in 15 months. Specifications evolving this fast break backwards compatibility. Agents built against an early MCP spec stop working when the spec updates. HiveMind, positioned as infrastructure, breaks all connected agents simultaneously when this happens.

**Why it happens:**
MCP's rapid adoption creates false stability signals. The fact that 17,000 servers exist does not mean the protocol is stable — it means there is massive adoption of something still being defined, which historically creates painful migration events (compare: early REST API versioning chaos, early GraphQL subscription instability).

**How to avoid:**
- Build a protocol abstraction layer between HiveMind's core and the MCP transport: the core should not call MCP primitives directly
- Version the HiveMind MCP interface independently from the upstream MCP spec
- Monitor the Anthropic MCP spec repository for breaking changes; subscribe to release notes
- Design the agent connection layer to be swappable: if MCP loses ecosystem traction, the connection mechanism must be replaceable without rebuilding the knowledge store
- Test against multiple MCP client implementations (Claude Desktop, Cursor, VS Code extension) — they have different compliance levels

**Warning signs:**
- MCP primitives are called directly throughout the codebase with no abstraction layer
- No integration tests run against the MCP spec's own conformance suite
- The team has not subscribed to upstream MCP changelog
- Agent connection code and knowledge storage code are in the same module

**Phase to address:** Phase 1 (architecture). The abstraction layer must be in place before any agent integration work begins.

---

### Pitfall 6: Crypto Layer Attracts Regulatory Scrutiny That Kills the Core Business

**What goes wrong:**
The agent-to-agent crypto trading feature (knowledge tokens, micropayments between agents) triggers securities regulation, money transmission licensing, and AML/KYC requirements in every jurisdiction where the platform operates. This is not a future risk — US regulators (SEC, FinCEN) and EU regulators (MiCA, which applies from December 2024) actively pursue platforms operating token-based systems without registration. A cease-and-desist or enforcement action against the crypto layer creates reputational and operational damage that brings down the core (non-crypto) product.

**Why it happens:**
The crypto layer is conceived as a differentiator and monetisation mechanism. The legal complexity is underestimated because the team focuses on technical implementation (smart contracts, token economics) rather than regulatory classification of what the tokens represent. If tokens can be traded for fiat, they are almost certainly securities or payment instruments under current regulatory frameworks.

**How to avoid:**
- Treat the crypto layer as a separate, legally isolated entity from day one — separate legal entity, separate infrastructure, separate ToS
- Do not launch the crypto layer until a jurisdiction-specific legal opinion has classified the tokens and confirmed the required licences
- Consider launching the core platform (MCP memory commons) first, without the crypto layer, to establish product-market fit and revenue without regulatory exposure
- If crypto is essential to the business model, engage a crypto-specialist law firm before writing the first line of smart contract code
- MiCA compliance (EU): register as a CASP (Crypto-Asset Service Provider) before operating in the EU

**Warning signs:**
- Token economics are being designed before legal classification of the tokens
- The crypto layer is in the same codebase and legal entity as the core platform
- No jurisdiction-specific legal opinion exists on token classification
- The team describes tokens as "not securities" based on internal reasoning rather than legal advice

**Phase to address:** Phase 0 (legal structure). Structural separation must be decided before any development begins on either layer.

---

### Pitfall 7: The Trust Paradox — Users Fear Contributing Because Contribution Is Visible

**What goes wrong:**
Agents contribute knowledge derived from their users' work sessions. Even with PII stripping, the contributed knowledge reveals: technology choices, architectural decisions, problem domains, competitive strategies, and implementation details. Enterprise users will not contribute if they believe competitors can access this information. The knowledge commons dies not from technical failure but from rational non-participation driven by confidentiality concerns.

The Stack Overflow research confirms this dynamic from the opposite direction: the platform's culture of hostile moderation caused participation to collapse before AI did. Perceived risk of exposure (being judged, downvoted, revealed as not knowing something) suppressed contribution. HiveMind's risks are higher — the exposure is not social embarrassment but competitive intelligence leakage.

**Why it happens:**
Builders of commons assume contributors share the builder's enthusiasm for open exchange. Enterprise procurement teams do not. A single security review that flags "your agent contributes knowledge to a shared external service" will block adoption across an entire organisation.

**How to avoid:**
- Design contribution controls that give enterprises genuine assurance, not just assurances: per-domain contribution rules (e.g. "never contribute knowledge from our healthcare domain"), per-tag exclusions, contribution preview before submission
- Implement a "private commons" mode: enterprises can pool knowledge within their own organisation without contributing to the public commons
- Publish a public technical specification of exactly what data leaves the agent and when — make it auditable, not just described in a privacy policy
- Third-party security audit of the contribution pipeline before enterprise sales begin
- Consider a selective contribution model: agents flag specific learnings as contribution candidates, humans approve before they enter the commons

**Warning signs:**
- There is no per-domain or per-tag contribution exclusion mechanism
- The contribution pipeline is not auditable by enterprise security teams
- Early enterprise prospects have not been asked about their security review requirements
- There is no private/enterprise commons option separate from the public commons

**Phase to address:** Phase 1 (contribution architecture) and Phase 2 (enterprise sales readiness).

---

### Pitfall 8: Knowledge IP Claimed by the Platform When It Cannot Be

**What goes wrong:**
The platform asserts ownership or exclusive rights over the knowledge commons, building a monetisation model around that ownership. This is legally fragile. The legal research establishes clearly: facts, data, and extracted knowledge are not protectable by copyright in either EU or US law (Feist Publications v. Rural Telephone, 499 U.S. 340, 1991; idea/expression dichotomy under TRIPS Art. 9(2)). AI-generated outputs have no copyright author (no human author = no copyright, confirmed US DC Circuit March 2025, CJUE harmonised standard). The EU Data Act (Regulation 2023/2854, Art. 43) explicitly excludes sui generis database rights for databases containing data generated through use of a product or service.

The platform "contractually owns" something it cannot legally protect. Competitors can copy the knowledge corpus without infringement.

**Why it happens:**
Legal analysis of IP in AI contexts often focuses on input copyright (training data) rather than output copyright. The conclusion that outputs have no protection surprises teams who assumed the platform's investment created defensible IP.

**How to avoid:**
- Do not build the business model on exclusive knowledge IP — it does not exist
- Build defensibility through: network effects (more agents = better knowledge), speed (first mover in verticals), integration depth (MCP + dashboard + vertical packs as a bundle), and human curation layer (the only path to copyright protection — substantial human creative selection and arrangement of outputs)
- If knowledge packs are sold, they must include substantial human-curated structure and commentary to approach copyright protection
- Open-source the core knowledge store structure while monetising access, tooling, and vertical-specific curation — this turns the absence of IP protection into a strategic advantage (openness attracts contributors)

**Warning signs:**
- The pitch deck claims the knowledge corpus is "proprietary" or "defensible IP"
- Legal review has not specifically addressed output copyright for AI-generated knowledge
- The business model's moat is described as "the knowledge we've accumulated" rather than "the network and tooling we've built"

**Phase to address:** Phase 0 (business model and legal structure). Affects fundraising narrative and monetisation design.

---

### Pitfall 9: Model Collapse Feedback Loop — The Commons Cannibalises Itself

**What goes wrong:**
Agents contribute AI-generated knowledge to the commons. Other agents retrieve that knowledge and use it to generate more AI outputs, which are contributed back. Over time, the commons contains increasingly synthetic knowledge with no human-validated signal. This is the "model collapse" problem documented by Shumailov et al. in Nature (2024): recursive training on AI-generated data causes "irreversible defects" — tail distribution cases disappear and outputs converge toward insipid averages. At 1/1000 contamination of synthetic data in training, the process can be triggered (ICLR 2025 Spotlight paper). The phenomenon is sometimes called "Habsburg AI" or "AI cannibalism."

For HiveMind specifically: if agents contribute the outputs of their LLM interactions without attribution of whether the knowledge was human-validated or AI-generated, the commons quality degrades silently. There is no way to detect this after the fact without provenance metadata.

**Why it happens:**
Knowledge origin is not tracked. "The agent learned this" is logged without distinguishing between: (a) the agent's user solved a problem and the agent observed it, (b) the agent hallucinated an answer that appeared plausible, (c) the agent retrieved something from a previous commons query and re-contributed it.

**How to avoid:**
- Tag every knowledge item with its origin type: human-validated, AI-generated, community-corroborated
- Implement contribution decay: knowledge not corroborated by independent sources over time decreases in confidence score rather than remaining static
- Explicitly block re-contribution of knowledge retrieved from the commons (circular contribution detection)
- Weight human-validated knowledge significantly higher than AI-generated knowledge in retrieval ranking
- Monitor knowledge quality metrics over time: if the distribution of knowledge types shifts toward pure-AI-generated, treat it as a systemic alert

**Warning signs:**
- Knowledge items do not carry an origin-type tag (human-observed vs. AI-generated)
- No circular contribution detection exists (agent retrieves from commons, generates an output, contributes the output back)
- Knowledge confidence scores do not decay without corroboration
- Quality metrics are limited to "number of items" rather than "ratio of human-corroborated items"

**Phase to address:** Phase 1 (data model). Provenance must be in the schema from the first insert.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Use Presidio vanilla without customisation | Fast PII pipeline to demo | F1 ~0.60 — misses French identifiers, misclassifies project names, leaks contextual PII in code metadata | Never in production |
| Single legal entity for core + crypto | Simpler structure, faster setup | Enforcement against crypto layer shuts down core platform | Never |
| Skip contribution validation gate at launch | Higher early contribution numbers | Poisoned commons that cannot be cleaned retroactively | Never |
| Seed commons manually from public sources | Solves cold start quickly | CC BY-SA licence obligations on Stack Overflow content must be tracked | Acceptable if licence compliance is documented |
| Tight coupling to MCP spec directly | Faster initial build | Breaking spec changes break all integrations simultaneously | Never beyond early prototype |
| Store knowledge without origin-type tag | Simpler schema | Cannot detect model collapse; cannot clean synthetic contamination | Never beyond proof-of-concept |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| MCP server | Assuming all MCP clients behave identically | Test against Claude Desktop, Cursor, and VS Code extension separately — compliance levels differ significantly |
| Anthropic/OpenAI Commercial API | Assuming commercial API ToS permits redistributing outputs as a knowledge product | ToS prohibit "resell the Services" — outputs used in a distinct product are permissible; treating the service itself as the product is not |
| Presidio (PII) | Using default configuration for French-language content | France has zero native recognisers by default; SIRET/SIREN, NIR, French phone formats require custom recognisers |
| Presidio (PII) | Running NER on code blocks | Code blocks contain variable names and path metadata that NER misclassifies; extract and preserve code blocks before analysis |
| Crypto/payment layer | Launching before MiCA CASP registration (EU) | MiCA applies from December 2024; operating as an unregistered CASP is an enforcement risk from day one |
| Stack Overflow data (seeding) | Treating as freely usable without attribution | Content is CC BY-SA 4.0 — requires attribution and share-alike; commercial use permitted but obligations apply |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Synchronous PII analysis on ingestion path | Ingestion latency exceeds MCP timeout thresholds; agents time out and disconnect | Move PII analysis to async pipeline; accept knowledge into quarantine queue first, release after validation | At >50 concurrent contributing agents |
| Real-time knowledge distribution to all agents | Fan-out storms when knowledge is updated; database write amplification | Implement pub/sub with per-agent subscription filtering; batch distribution with configurable freshness lag | At >500 connected agents |
| Single-pass NER on long documents | Missed PII at document boundaries; context window truncation causes false negatives | Chunk documents with overlap; run NER on chunks, merge results with deduplication | All production-length agent outputs |
| No knowledge deduplication | Commons size grows without utility growing; retrieval noise increases | Content-addressed storage (hash-based deduplication) with semantic similarity clustering | At >100K knowledge items |
| Synchronous knowledge validation | Contributes block on validation queue depth | Async validation with quarantine state; contributors receive acknowledgement, not confirmation | At >10 concurrent contributors |

---

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Storing PII mapping tables in the same database as anonymised knowledge | Re-identification attack: attacker who gains read access to both tables can de-anonymise the entire corpus | Separate storage systems for pseudonymisation maps; encrypt maps at rest with keys not accessible to knowledge store |
| No rate limiting on agent knowledge contribution | Single malicious agent floods the commons with poisoned knowledge at machine speed | Per-agent contribution rate limits; burst detection; new agents start in probationary tier with lower limits |
| Knowledge retrieval without access scoping | Enterprise agent retrieves knowledge contributed by competitor's agent in same vertical | Implement contribution visibility controls: public, organisation-scoped, vertical-scoped, private |
| Crypto private keys in agent connection metadata | Key extraction from memory or logs compromises agent wallets | Never store private keys server-side; agent handles its own keys; platform receives only signed transactions |
| No audit log of what knowledge each agent retrieved | Cannot investigate breach or poisoning event post-hoc | Immutable retrieval audit log: agent ID, query, knowledge items returned, timestamp |
| Relying on ToS to prevent misuse | ToS is not a technical control; malicious agents do not comply | Technical controls (rate limits, contribution validation, circuit breakers) are the actual defence |

---

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| No contribution preview | Enterprise users cannot review what their agent will contribute before it is shared; security teams block adoption | Show agents a "pending contribution" queue with human review option before publication |
| Binary public/private contribution | Users either share everything or nothing; most choose nothing | Granular controls: per-domain, per-tag, per-confidence-level contribution rules |
| No feedback when retrieved knowledge is wrong | Agent uses bad knowledge; developer cannot report it; poisoned knowledge remains in commons | Every retrieved knowledge item must have a "flag as incorrect" mechanism tied to the contributing agent's reputation |
| Commons presented as a search engine | Users expect Google-like recall and precision; knowledge commons has much lower coverage | Frame as "collective memory" with explicit confidence scores; set expectations around coverage gaps |
| Crypto wallet required to use core features | Non-crypto users cannot access the platform at all | Crypto layer is optional; core MCP memory functions require no wallet or token |

---

## "Looks Done But Isn't" Checklist

- [ ] **PII Pipeline:** Detects and handles French-specific identifiers (NIR, SIRET, SIREN), internal URLs, git metadata author fields, file paths, and project codenames — not just person names and emails
- [ ] **Consent Flow:** Consent for extraction, processing, and commercialisation are three separate, independently revocable consent events — not a single ToS checkbox
- [ ] **Knowledge Provenance:** Every knowledge item carries origin type (human-observed, AI-generated, community-corroborated), contributing agent ID, timestamp, and corroboration count — not just content
- [ ] **Cold Start:** The commons contains useful knowledge for at least one target vertical before the first external agent connects — not seeded on-demand after complaints
- [ ] **MCP Abstraction:** The protocol transport layer is behind an abstraction interface with at least two adapters tested — not direct MCP primitive calls throughout the codebase
- [ ] **Contribution Validation:** No knowledge is distributed to other agents without passing at least an automated confidence gate — not accepted and immediately fan-out
- [ ] **Circular Contribution Detection:** The system can detect when an agent retrieves knowledge from the commons and attempts to contribute it back — not just trusting agents not to do this
- [ ] **Legal Entity Separation:** The crypto layer operates under a separate legal entity from the core platform — not the same company with a separate GitHub repo

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| PII leakage discovered post-launch | HIGH | GDPR breach notification within 72h; engage DPO and legal; assess scope; notify affected users; potential model deletion order |
| Commons poisoned with bad knowledge | HIGH | Quarantine all knowledge from suspect agents; audit corroboration chains; retract contaminated items; rebuild confidence scores from scratch |
| Cold start failure at launch | MEDIUM | Emergency seeding sprint from public sources; temporarily gate access to a closed beta while commons reaches minimum useful threshold |
| MCP spec breaking change breaks all integrations | MEDIUM | Roll back to abstraction layer adapter; implement new adapter in parallel; release with version negotiation |
| Crypto enforcement action | HIGH | Immediately halt crypto operations; engage regulatory counsel; assess liability to core entity; communicate to users |
| Trust collapse — enterprises stop contributing | HIGH | There is no recovery without architectural changes to contribution controls; prevention is the only viable strategy |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| PII stripping treated as legal shield | Phase 1: ingestion architecture | DPIA completed; test suite includes membership inference attack simulation; French identifiers in test corpus |
| No viable legal basis for private conversation commercialisation | Phase 0: business model | Legal opinion obtained for EU + US; consent flows reviewed by DPO; machine unlearning mechanism specified |
| Knowledge poisoning | Phase 1: ingestion pipeline | Contribution validation gate in place; knowledge quarantine state in data model; new agent rate limits configured |
| Cold start / empty commons | Phase 0 + Phase 1 | Minimum viable commons threshold defined; seeding pipeline runs before external access opens; at least one vertical has 1000+ curated items |
| MCP protocol instability | Phase 1: architecture | Protocol abstraction layer exists; two MCP client implementations tested; abstraction layer has its own test suite |
| Crypto regulatory exposure | Phase 0: legal structure | Separate legal entity for crypto layer; jurisdiction-specific legal opinion on token classification obtained |
| Trust paradox / enterprise refusal | Phase 1 + Phase 2 | Per-domain contribution exclusions work; enterprise pilot security review passed; private commons mode available |
| Knowledge IP non-defensibility | Phase 0: business model | Pitch deck does not claim "proprietary knowledge IP"; moat is described in terms of network effects and tooling |
| Model collapse / synthetic contamination | Phase 1: data model | Origin-type field in schema; circular contribution detection in tests; knowledge decay algorithm specified |

---

## Sources

- **Primary:** "Risques juridiques majeurs d'une plateforme de revente de connaissances IA" (deep research PDF, 2025) — GDPR, ePrivacy, AI Act, copyright, trade secrets, provider ToS analysis
- **Primary:** "Anonymisation automatique des données LLM : état de l'art technique 2025" (deep research PDF, 2025) — Presidio architecture, NER benchmarks, PII edge cases for agent memory files
- **Primary:** "La grande extinction silencieuse du savoir technique collectif" (deep research PDF, 2025/2026) — Stack Overflow collapse data, dark knowledge phenomenon, model collapse research, MCP ecosystem data
- **Primary:** "L'effondrement de Stack Overflow et la crise silencieuse du savoir développeur" (deep research PDF, 2025/2026) — quantitative decline data, developer trust paradox, emerging knowledge ecosystem landscape
- **Legal cases cited in research:** Thaler v. Perlmutter (DC Circuit, March 2025); Feist Publications v. Rural Telephone (499 U.S. 340, 1991); West Technology Group v. Sundstrom (D. Conn., 2024); Garcia v. Character Technologies (M.D. Fla., May 2025)
- **Regulatory actions cited in research:** Italian Garante vs. OpenAI (Nov 2024, EUR 15M); CNIL vs. Google (Sept 2025, EUR 325M); EDPB Opinion 28/2024; CNIL guidance June/July 2025
- **Academic research cited in research:** Shumailov et al., Nature 2024 (model collapse); Del Rio-Chanona et al., PNAS Nexus Sept 2024 (Stack Overflow causal impact study); ICLR 2025 Spotlight (1/1000 synthetic data contamination threshold)

---
*Pitfalls research for: Shared AI Agent Memory / Knowledge Commons (HiveMind)*
*Researched: 2026-02-18*

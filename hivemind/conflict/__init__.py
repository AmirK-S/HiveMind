"""LLM-assisted conflict resolution for HiveMind knowledge contributions (KM-07).

When the dedup pipeline detects a near-duplicate, the conflict resolver determines
the appropriate action:
  UPDATE       — new knowledge supersedes existing (newer version, corrected info)
  ADD          — new knowledge is distinct enough to coexist (different angle)
  NOOP         — new knowledge adds nothing beyond existing (near-exact duplicate)
  VERSION_FORK — both are valid but for different versions/contexts (e.g. Python 3.11 vs 3.12)

Multi-hop conflicts (requiring reasoning over multiple items) are explicitly
flagged for human review rather than auto-resolved (per KM-07 constraint).
"""

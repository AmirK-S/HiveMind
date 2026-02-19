"""Near-duplicate detection pipeline for HiveMind (KM-03).

Three-stage dedup pipeline:
  Stage 1 (Cosine): Finds top-K candidates by embedding similarity.
  Stage 2 (MinHash): Filters to lexical near-duplicates via Jaccard similarity.
  Stage 3 (LLM): Confirms semantic duplicates above configurable confidence threshold.
"""

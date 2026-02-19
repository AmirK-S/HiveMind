"""Quality Intelligence module for HiveMind (Phase 3).

Public API:
- scorer.compute_quality_score : compute quality score from behavioral signals
- signals.record_signal         : insert a behavioral signal for a knowledge item
- signals.get_signals_for_item  : retrieve all signals for a knowledge item
- signals.increment_retrieval_count : atomically increment retrieval counter
"""

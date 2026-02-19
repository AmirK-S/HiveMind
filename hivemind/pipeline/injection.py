"""
Prompt injection scanner for HiveMind.

Uses ProtectAI/deberta-v3-base-prompt-injection-v2 via the transformers pipeline
to classify text as benign (LABEL_0) or injection (LABEL_1).

Requirements addressed:
  - SEC-01: Contributed knowledge scanned for prompt injection and malicious
    instructions before entering commons.

Design decisions:
- Singleton pattern (class-level _instance + get_instance()) mirrors PIIPipeline.
- All heavy imports (transformers, torch) are deferred to __init__ so the module
  can be imported without triggering a multi-second model load at startup.
- _MAX_INPUT_CHARS caps input to 2000 characters before passing to the pipeline
  to prevent OOM on very long inputs; the model tokenizer further truncates to
  512 tokens via truncation=True.
- is_injection() returns (bool, float) so callers can log the confidence score
  without re-running the model.

Usage:
    is_injection, score = InjectionScanner.get_instance().is_injection(raw_text)
    if is_injection:
        # Reject contribution
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from transformers import Pipeline

_MODEL_ID = "ProtectAI/deberta-v3-base-prompt-injection-v2"
_THRESHOLD = 0.5
_MAX_INPUT_CHARS = 2000  # truncate to prevent OOM on very long inputs


class InjectionScanner:
    """Singleton prompt injection scanner using DeBERTa-v3.

    Lazily loads the ProtectAI/deberta-v3-base-prompt-injection-v2 model on
    first instantiation. Subsequent calls to get_instance() return the cached
    singleton without reloading the model.

    Usage:
        is_injection, score = InjectionScanner.get_instance().is_injection(text)
    """

    _instance: "InjectionScanner | None" = None

    def __init__(self, threshold: float = _THRESHOLD) -> None:
        # Lazy imports: transformers + torch are large; defer until first
        # instantiation so `from hivemind.pipeline.injection import InjectionScanner`
        # does not block on model disk I/O at import time.
        from transformers import (  # noqa: PLC0415
            AutoModelForSequenceClassification,
            AutoTokenizer,
            pipeline,
        )
        import torch  # noqa: PLC0415

        self._threshold = threshold
        tokenizer = AutoTokenizer.from_pretrained(_MODEL_ID)
        model = AutoModelForSequenceClassification.from_pretrained(_MODEL_ID)
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self._pipeline: "Pipeline" = pipeline(
            "text-classification",
            model=model,
            tokenizer=tokenizer,
            truncation=True,
            max_length=512,
            device=device,
        )

    @classmethod
    def get_instance(cls) -> "InjectionScanner":
        """Return the module-level singleton, creating it on first call."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def is_injection(
        self,
        text: str,
        threshold: float | None = None,
    ) -> tuple[bool, float]:
        """Classify *text* as injection or benign.

        Args:
            text: Raw input text. Truncated to _MAX_INPUT_CHARS internally.
            threshold: Override the instance-level threshold for this call.
                       Defaults to self._threshold (_THRESHOLD = 0.5).

        Returns:
            (is_injection, score) where is_injection is True when the model
            classifies the text as prompt injection with confidence >= threshold,
            and score is the raw confidence of the winning label.

        Label semantics (per Hugging Face model card):
            LABEL_0 = benign
            LABEL_1 = injection
        """
        effective_threshold = threshold if threshold is not None else self._threshold
        result = self._pipeline(text[:_MAX_INPUT_CHARS])
        label: str = result[0]["label"]
        score: float = result[0]["score"]
        return (label == "LABEL_1" and score >= effective_threshold), score

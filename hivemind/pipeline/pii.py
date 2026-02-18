"""
PII stripping pipeline for HiveMind.

Multi-layer approach:
  1. Presidio AnalyzerEngine — built-in recognizers (email, phone, credit card, SSN, etc.)
  2. GLiNERRecognizer — zero-shot NER via knowledgator/gliner-pii-base-v1.0
  3. Custom PatternRecognizer — API keys, tokens, secrets, connection strings, private URLs

Design decisions (per user):
- Silent stripping: no logging of what was detected, no before/after comparison
- PII stripped BEFORE any storage — raw text is never persisted
- Code snippets are stripped too — safety first
- Auto-reject if placeholder tokens exceed 50% of post-strip token count
- Typed placeholders for confident entity types; [REDACTED] as fallback

Import strategy:
- presidio_analyzer and presidio_anonymizer are imported lazily inside
  PIIPipeline.__init__ and helper functions to avoid loading spacy at module
  import time. spacy 3.8 uses Pydantic v1 which is incompatible with Python
  3.14 at import time but works at runtime once the C extensions are loaded.
  Lazy imports allow `from hivemind.pipeline.pii import strip_pii` to work
  without triggering the spacy import chain until PIIPipeline is first used.

Exports: PIIPipeline, strip_pii
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # Type-checking only — not imported at runtime until PIIPipeline.__init__
    from presidio_analyzer import AnalyzerEngine, PatternRecognizer, Pattern
    from presidio_analyzer.predefined_recognizers import GLiNERRecognizer
    from presidio_anonymizer import AnonymizerEngine
    from presidio_anonymizer.entities import OperatorConfig


# ---------------------------------------------------------------------------
# Placeholder regex — used for the 50% rejection check
# Matches all typed placeholders produced by the operator config below
# ---------------------------------------------------------------------------
_PLACEHOLDER_RE = re.compile(
    r'\[(?:EMAIL|PHONE|NAME|LOCATION|API_KEY|CREDIT_CARD|IP_ADDRESS|USERNAME|REDACTED)\]'
)


def _build_api_key_patterns() -> list:
    """Return curated regex patterns for API keys, secrets, and private URLs."""
    # Local import to avoid triggering spacy at module load time
    from presidio_analyzer import Pattern  # noqa: PLC0415

    return [
        # AWS access key ID
        Pattern("aws_key", r"AKIA[0-9A-Z]{16}", 0.9),
        # GitHub personal access token (classic)
        Pattern("github_token_classic", r"ghp_[A-Za-z0-9]{36}", 0.9),
        # GitHub personal access token (fine-grained)
        Pattern("github_token_fine_grained", r"github_pat_[A-Za-z0-9_]{82}", 0.9),
        # Google API key
        Pattern("google_api_key", r"AIza[0-9A-Za-z\-_]{35}", 0.9),
        # Stripe secret or publishable key
        Pattern("stripe_key", r"(?:sk|pk)_(?:test|live)_[A-Za-z0-9]{24,}", 0.9),
        # Slack token (bot, app, user, workspace, etc.)
        Pattern("slack_token", r"xox[baprs]-[A-Za-z0-9-]+", 0.85),
        # JSON Web Token
        Pattern("jwt", r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", 0.85),
        # PEM private key header
        Pattern("rsa_private_key", r"-----BEGIN (?:RSA )?PRIVATE KEY-----", 0.95),
        # Generic secret assignment (api_key=..., password=..., etc.)
        Pattern(
            "generic_secret",
            r"(?i)(?:api[_-]?key|secret[_-]?key|access[_-]?token|auth[_-]?token|password|passwd|pwd)\s*[:=]\s*['\"]?\S{8,}['\"]?",
            0.7,
        ),
        # Database / service connection strings
        Pattern(
            "connection_string",
            r"(?i)(?:postgres(?:ql)?|mysql|mongodb|redis|amqp)://\S+",
            0.9,
        ),
        # Private / localhost URLs
        Pattern(
            "private_url",
            r"(?:https?://)?(?:localhost|127\.0\.0\.1|10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+|172\.(?:1[6-9]|2\d|3[01])\.\d+\.\d+)(?::\d+)?(?:/\S*)?",
            0.7,
        ),
    ]


def _build_operator_config() -> dict:
    """Return typed-placeholder operator config for Presidio anonymizer."""
    # Local import to avoid triggering spacy at module load time
    from presidio_anonymizer.entities import OperatorConfig  # noqa: PLC0415

    return {
        # Standard Presidio entity types
        "EMAIL_ADDRESS": OperatorConfig("replace", {"new_value": "[EMAIL]"}),
        "PHONE_NUMBER": OperatorConfig("replace", {"new_value": "[PHONE]"}),
        "PERSON": OperatorConfig("replace", {"new_value": "[NAME]"}),
        "LOCATION": OperatorConfig("replace", {"new_value": "[LOCATION]"}),
        "CREDIT_CARD": OperatorConfig("replace", {"new_value": "[CREDIT_CARD]"}),
        "IP_ADDRESS": OperatorConfig("replace", {"new_value": "[IP_ADDRESS]"}),
        "US_SSN": OperatorConfig("replace", {"new_value": "[REDACTED]"}),
        "PASSWORD": OperatorConfig("replace", {"new_value": "[REDACTED]"}),
        "USERNAME": OperatorConfig("replace", {"new_value": "[USERNAME]"}),
        # Custom entity from API key recognizer
        "API_KEY": OperatorConfig("replace", {"new_value": "[API_KEY]"}),
        # Fallback for any entity type not listed above
        "DEFAULT": OperatorConfig("replace", {"new_value": "[REDACTED]"}),
    }


class PIIPipeline:
    """Singleton PII stripping pipeline.

    Loads Presidio + GLiNER + custom recognizers once at construction time.
    The GLiNER model (~400 MB) is expensive to load — use get_instance() to
    avoid duplicate loads.

    Usage:
        cleaned_text, should_reject = PIIPipeline.get_instance().strip(raw_text)
    """

    _instance: "PIIPipeline | None" = None

    def __init__(self) -> None:
        # Lazy imports: presidio pulls in spacy which fails to import on Python 3.14
        # at module load time due to Pydantic v1 incompatibility. Deferring the import
        # to __init__ means spacy is only loaded when PIIPipeline is first instantiated
        # (at server startup lifespan), not when the module is imported.
        from presidio_analyzer import AnalyzerEngine, PatternRecognizer  # noqa: PLC0415
        from presidio_analyzer.predefined_recognizers import GLiNERRecognizer  # noqa: PLC0415
        from presidio_anonymizer import AnonymizerEngine  # noqa: PLC0415

        # --- Analyzer setup ---
        self._analyzer = AnalyzerEngine()

        # GLiNER recognizer: zero-shot NER for names, addresses, health data, etc.
        # Entity mapping: GLiNER label -> Presidio entity type
        gliner_entity_mapping = {
            "name": "PERSON",
            "email address": "EMAIL_ADDRESS",
            "phone number": "PHONE_NUMBER",
            "location address": "LOCATION",
            "password": "PASSWORD",
            "username": "USERNAME",
            "credit card number": "CREDIT_CARD",
            "date of birth": "DATE_TIME",
            "social security number": "US_SSN",
            "driver's license": "US_DRIVER_LICENSE",
            "passport number": "US_PASSPORT",
            "bank account number": "US_BANK_NUMBER",
            "ip address": "IP_ADDRESS",
            "medical record number": "MEDICAL_LICENSE",
            "health insurance id": "MEDICAL_LICENSE",
        }
        gliner_recognizer = GLiNERRecognizer(
            model_name="knowledgator/gliner-pii-base-v1.0",
            entity_mapping=gliner_entity_mapping,
            flat_ner=False,
            multi_label=True,
            map_location="cpu",
        )
        self._analyzer.registry.add_recognizer(gliner_recognizer)

        # Custom recognizer for API keys, tokens, secrets, and private URLs
        api_key_recognizer = PatternRecognizer(
            supported_entity="API_KEY",
            patterns=_build_api_key_patterns(),
        )
        self._analyzer.registry.add_recognizer(api_key_recognizer)

        # --- Anonymizer setup ---
        self._anonymizer = AnonymizerEngine()
        self._operators = _build_operator_config()

    @classmethod
    def get_instance(cls) -> "PIIPipeline":
        """Return the module-level singleton, creating it on first call."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def strip(self, text: str) -> tuple[str, bool]:
        """Strip PII from *text* and return (cleaned_text, should_reject).

        Args:
            text: Raw input content (may contain emails, keys, names, etc.)

        Returns:
            cleaned_text: Content with PII replaced by typed placeholders.
            should_reject: True if >50% of post-strip tokens are placeholders,
                           indicating the content is too redacted to be useful.

        This method is intentionally SILENT — it does not log what was detected
        or produce before/after comparisons. The caller only ever sees the cleaned
        version.
        """
        # Step 1: detect entities
        results = self._analyzer.analyze(text=text, language="en")

        # Step 2: replace entities with typed placeholders
        anonymized = self._anonymizer.anonymize(
            text=text,
            analyzer_results=results,
            operators=self._operators,
        )
        cleaned = anonymized.text

        # Step 3: 50% rejection check
        # Count placeholder tokens in the anonymized text and compare to total
        # token count. Using the POST-strip token count (not original) avoids
        # inflation from multi-word names collapsing into a single [NAME] token.
        placeholder_count = len(_PLACEHOLDER_RE.findall(cleaned))
        total_tokens = max(len(cleaned.split()), 1)
        should_reject = (placeholder_count / total_tokens) > 0.50

        return cleaned, should_reject


def strip_pii(text: str) -> tuple[str, bool]:
    """Module-level convenience wrapper around PIIPipeline.get_instance().strip().

    Args:
        text: Raw input content.

    Returns:
        (cleaned_text, should_reject) — see PIIPipeline.strip() for details.
    """
    return PIIPipeline.get_instance().strip(text)

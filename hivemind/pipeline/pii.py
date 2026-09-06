"""
PII stripping pipeline for HiveMind.

Multi-layer approach:
  1. Presidio AnalyzerEngine, built-in recognizers (email, phone, credit card, SSN, etc.)
  2. GLiNERRecognizer, zero-shot NER via knowledgator/gliner-pii-base-v1.0
  3. Custom PatternRecognizer, API keys, tokens, secrets, connection strings, private URLs

Design decisions (per user):
- Silent stripping: no logging of what was detected, no before/after comparison
- PII stripped BEFORE any storage, raw text is never persisted
- Markdown-aware: fenced and inline code blocks are preserved intact (TRUST-06)
- Two-pass validation: re-analyze anonymized text + verbatim check (TRUST-05)
- Auto-reject if placeholder tokens exceed 50% of post-strip token count
- Typed placeholders for confident entity types; [REDACTED] as fallback

Import strategy:
- presidio_analyzer and presidio_anonymizer are imported lazily inside
  PIIPipeline.__init__ and helper functions to avoid loading spacy at module
  import time. spacy 3.8 uses Pydantic v1 which is incompatible with Python
  3.14 at import time but works at runtime once the C extensions are loaded.
  Lazy imports allow `from hivemind.pipeline.pii import strip_pii` to work
  without triggering the spacy import chain until PIIPipeline is first used.

Exports: PIIPipeline, strip_pii, _extract_code_blocks, _reinject_code_blocks
"""

from __future__ import annotations

import re
import uuid
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # Type-checking only, not imported at runtime until PIIPipeline.__init__
    from presidio_analyzer import AnalyzerEngine, PatternRecognizer, Pattern
    from presidio_analyzer.predefined_recognizers import GLiNERRecognizer
    from presidio_anonymizer import AnonymizerEngine
    from presidio_anonymizer.entities import OperatorConfig


# ---------------------------------------------------------------------------
# Placeholder regex: used for the 50% rejection check
# Matches all typed placeholders produced by the operator config below
# ---------------------------------------------------------------------------
_PLACEHOLDER_RE = re.compile(
    r'\[(?:EMAIL|PHONE|NAME|LOCATION|API_KEY|CREDIT_CARD|IP_ADDRESS|USERNAME|REDACTED)\]'
)

# ---------------------------------------------------------------------------
# GLiNER confidence floor.
# Below that, package names such as asyncpg match the zero-shot label API_KEY:
# the technical false positives measured sit between 0.30 and 0.51, the real
# secrets, names and addresses between 0.79 and 0.93.
# ---------------------------------------------------------------------------
_GLINER_THRESHOLD = 0.60

# ---------------------------------------------------------------------------
# Entity types the analyzer is asked for, in a fixed order.
# Passing all registered entities let the pattern recognizer name API_KEY leak
# into GLiNER as a zero-shot label, and the set order made results differ per
# process: AnalyzerEngine derives the list from list(set(...)) when entities is
# omitted, and GLiNERRecognizer appends whatever it does not recognise to its
# prompt labels, in that order. A literal list has a fixed order and only names
# the types the operator config below actually types.
# ---------------------------------------------------------------------------
_REQUESTED_ENTITIES = [
    "PERSON",
    "EMAIL_ADDRESS",
    "PHONE_NUMBER",
    "LOCATION",
    "PASSWORD",
    "USERNAME",
    "CREDIT_CARD",
    "US_SSN",
    "US_DRIVER_LICENSE",
    "US_PASSPORT",
    "US_BANK_NUMBER",
    "IP_ADDRESS",
    "MEDICAL_LICENSE",
    "IBAN_CODE",
    "API_KEY",
]

# ---------------------------------------------------------------------------
# Code block extraction regexes (TRUST-06)
# Fenced code blocks: ```...``` or ~~~...~~~
# Inline code spans: `...`
# Order of application matters: fenced first, then inline, this ensures
# triple-backtick fenced blocks are already replaced before the inline regex
# runs, avoiding false matches on the opening/closing triple backticks.
# (See Phase 2 research: Pitfall 5)
# ---------------------------------------------------------------------------
_FENCED_CODE_RE = re.compile(r'(```[\s\S]*?```|~~~[\s\S]*?~~~)', re.MULTILINE)
_INLINE_CODE_RE = re.compile(r'(`[^`\n]+`)')
# The placeholders themselves. The analyzer must never touch them: a hex run
# inside the token gets classified now and then (PERSON at 0.85 by spaCy,
# MEDICAL_LICENSE at 1.00 on nine digits in a row), the key is anonymized away
# and _reinject_code_blocks silently loses the whole block, password included.
_CODE_TOKEN_RE = re.compile(r'__(?:CODE_BLOCK|INLINE)_[0-9a-f]{32}__')


def _drop_results_over_code_tokens(text: str, results: list) -> list:
    """Remove analyzer results that overlap a code block placeholder in *text*."""
    token_spans = [m.span() for m in _CODE_TOKEN_RE.finditer(text)]
    if not token_spans:
        return results
    return [
        r for r in results
        if all(r.end <= start or end <= r.start for start, end in token_spans)
    ]


def _extract_code_blocks(text: str) -> tuple[str, dict[str, str]]:
    """Replace fenced and inline code blocks with UUID placeholders.

    Fenced blocks (``` or ~~~) are replaced first with ``__CODE_BLOCK_{hex}__``
    placeholders. Inline backtick spans are replaced second with
    ``__INLINE_{hex}__`` placeholders. The original values are stored in the
    returned mapping so they can be reinjected intact after PII stripping.

    Args:
        text: Raw markdown text potentially containing code blocks.

    Returns:
        (modified_text, placeholder_map) where placeholder_map maps each
        placeholder key to the original code block string.
    """
    placeholder_map: dict[str, str] = {}

    def replace_fenced(m: re.Match) -> str:  # type: ignore[type-arg]
        key = f"__CODE_BLOCK_{uuid.uuid4().hex}__"
        placeholder_map[key] = m.group(0)
        return key

    def replace_inline(m: re.Match) -> str:  # type: ignore[type-arg]
        key = f"__INLINE_{uuid.uuid4().hex}__"
        placeholder_map[key] = m.group(0)
        return key

    text = _FENCED_CODE_RE.sub(replace_fenced, text)
    text = _INLINE_CODE_RE.sub(replace_inline, text)
    return text, placeholder_map


def _reinject_code_blocks(text: str, placeholder_map: dict[str, str]) -> str:
    """Restore original code blocks by replacing placeholders in *text*.

    Args:
        text: Anonymized text that may contain ``__CODE_BLOCK_*__`` or
              ``__INLINE_*__`` placeholders from a prior _extract_code_blocks call.
        placeholder_map: Mapping from placeholder key to original code block.

    Returns:
        Text with all placeholders replaced by their original code block content.
    """
    for key, original in placeholder_map.items():
        text = text.replace(key, original)
    return text


_SPAN_MASK_CHAR = "\x00"


def _mask_spans(text: str, results: list) -> str:
    """Return *text* with every analyzer span blanked out.

    Used by the pass 2b verbatim check to count the occurrences of a value the
    analyzer did NOT flag, so those occurrences are left in place.

    Args:
        text: The narrative text the analyzer ran on.
        results: The RecognizerResult objects returned for that text.

    Returns:
        A string of the same length, with the detected spans replaced by a
        character that cannot appear in a detected value.
    """
    chars = list(text)
    for result in results:
        for index in range(max(result.start, 0), min(result.end, len(chars))):
            chars[index] = _SPAN_MASK_CHAR
    return "".join(chars)


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
        # Anthropic API key (dashes, not the underscores of the Stripe format)
        Pattern("anthropic_key", r"sk-ant-api\d{2}-[A-Za-z0-9_-]{32,}", 0.95),
        # OpenAI project key
        Pattern("openai_project_key", r"sk-proj-[A-Za-z0-9_-]{32,}", 0.95),
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
    The GLiNER model (~400 MB) is expensive to load, use get_instance() to
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
            threshold=_GLINER_THRESHOLD,
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

        Implements TRUST-05 (two-pass validation) and TRUST-06 (markdown-aware
        code block preservation).

        Args:
            text: Raw input content (may contain emails, keys, names, etc.)

        Returns:
            cleaned_text: Content with PII replaced by typed placeholders.
                          Fenced and inline code blocks are preserved intact.
            should_reject: True if >50% of post-strip tokens are placeholders,
                           indicating the content is too redacted to be useful.

        This method is intentionally SILENT, it does not log what was detected
        or produce before/after comparisons. The caller only ever sees the cleaned
        version.

        Two-pass validation (TRUST-05):
            Pass 1: Standard Presidio analysis + anonymization on narrative text.
            Pass 2a: Re-run analyzer on anonymized output; re-strip any residual.
            Pass 2b: Verbatim check: if any original PII value (len >= 4) still
                      appears literally in the output, replace with [REDACTED].

        Markdown-aware (TRUST-06):
            Fenced code blocks (``` or ~~~) and inline code spans (`) are
            extracted before any analysis and reinjected intact afterward.
            PII inside code blocks is never stripped.
        """
        # TRUST-06: Extract code blocks before any PII analysis.
        # The narrative text (no code blocks) is what we analyze for PII.
        narrative, code_map = _extract_code_blocks(text)

        # Pass 1: detect and anonymize PII in narrative text
        results = self._analyzer.analyze(
            text=narrative, language="en", entities=_REQUESTED_ENTITIES
        )
        results = _drop_results_over_code_tokens(narrative, results)

        # Capture original PII values for the verbatim check (Pass 2b).
        # We collect them here, before anonymization modifies the text.
        original_pii_values = [narrative[r.start:r.end] for r in results]

        anonymized = self._anonymizer.anonymize(
            text=narrative,
            analyzer_results=results,
            operators=self._operators,
        )
        cleaned_narrative = anonymized.text

        # TRUST-05 Pass 2a: re-run analyzer on anonymized text.
        # Presidio may miss PII that becomes visible only after surrounding
        # context is removed (e.g., a name next to a redacted email). Re-strip
        # any residual findings.
        # It must not re-read its own markers: GLiNER scores the word API_KEY
        # inside [API_KEY] higher than the text that produced it, which is what
        # turned [API_KEY] into [[API_KEY]]. Findings that fall inside, or across
        # the edge of, a placeholder written by pass 1 are dropped; a finding
        # that covers a whole placeholder plus surrounding text is kept.
        residual_results = self._analyzer.analyze(
            text=cleaned_narrative, language="en", entities=_REQUESTED_ENTITIES
        )
        residual_results = _drop_results_over_code_tokens(cleaned_narrative, residual_results)
        marker_spans = [m.span() for m in _PLACEHOLDER_RE.finditer(cleaned_narrative)]
        residual_results = [
            r
            for r in residual_results
            if all(
                r.end <= start or end <= r.start or (r.start <= start and end <= r.end)
                for start, end in marker_spans
            )
        ]
        if residual_results:
            cleaned_narrative = self._anonymizer.anonymize(
                text=cleaned_narrative,
                analyzer_results=residual_results,
                operators=self._operators,
            ).text

        # TRUST-05 Pass 2b: verbatim check, bounded to the detected positions.
        # For each original PII value of length >= 4, check if it literally
        # survived into the output. Length threshold avoids false positives from
        # single-character or very short fragments (see Phase 2 research: Pitfall 4).
        # The replacement used to be a global str.replace(), which also erased the
        # occurrences the analyzer never flagged: once "nginx" was detected in
        # "behind nginx:", /etc/nginx/nginx.conf became
        # /etc/[REDACTED]/[REDACTED][REDACTED]. Counting the occurrences that lie
        # outside every detected span tells the two apart: the value is only
        # replaced when more of them survived than were left untouched on purpose.
        masked_narrative = _mask_spans(narrative, results)
        for pii_value in dict.fromkeys(original_pii_values):
            if len(pii_value) < 4:
                continue
            untouched = masked_narrative.count(pii_value)
            if cleaned_narrative.count(pii_value) > untouched:
                cleaned_narrative = cleaned_narrative.replace(pii_value, "[REDACTED]")

        # TRUST-06: Reinject code blocks intact.
        # The PII scanner never touched these blocks.
        cleaned = _reinject_code_blocks(cleaned_narrative, code_map)

        # 50% rejection check on POST-strip token count (existing decision).
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
        (cleaned_text, should_reject), see PIIPipeline.strip() for details.
    """
    return PIIPipeline.get_instance().strip(text)

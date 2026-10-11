"""Find and replace card data and personal data in free text before it is stored or sent to an LLM (Phase 3).

Card numbers that pass the Luhn check are swapped for vault tokens, so support staff can still
correlate them internally. Everything else is replaced with a typed placeholder. The patterns lean
toward over-redaction: losing an order number in a summary is cheap, leaking a card number is not.
"""
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Callable

# 13-19 digits, optionally separated by single spaces or dashes ("4111 1111 1111 1111").
PAN_CANDIDATE = re.compile(r"(?<!\d)\d(?:[ -]?\d){12,18}(?!\d)")
CVV = re.compile(r"\b(?:cvv2?|cvc2?|cid|security\s+code)\b\W{0,3}\d{3,4}\b", re.IGNORECASE)
EXPIRY = re.compile(
    r"\b(?:exp(?:iry|iration|ires)?(?:\s+date)?)\b\W{0,3}(?:0?[1-9]|1[0-2])\s*[/-]\s*(?:\d{4}|\d{2})\b",
    re.IGNORECASE,
)
SSN = re.compile(r"(?<!\d)\d{3}-\d{2}-\d{4}(?!\d)")
PHONE = re.compile(r"(?<![\d-])(?:\+?1[ .-]?)?(?:\(\d{3}\)\s?|\d{3}[ .-])\d{3}[ .-]\d{4}(?!\d)")
EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]{1,64}@(?:[A-Za-z0-9-]{1,63}\.){1,8}[A-Za-z]{2,24}\b")  # bounded: no runaway backtracking
LONG_NUMBER = re.compile(r"(?<!\d)\d{9,}(?!\d)")  # account, routing, or unformatted ID numbers


class UnsafePayload(Exception):
    """Something that looks like a card number survived redaction; the request must not leave."""


@dataclass
class Redaction:
    text: str
    counts: dict[str, int] = field(default_factory=dict)


def luhn_valid(digits: str) -> bool:
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch)
        if i % 2 == 1:
            d = d * 2 - 9 if d > 4 else d * 2
        total += d
    return total % 10 == 0


class Redactor:
    def __init__(self, tokenize_pan: Callable[[str], str | None] | None = None):
        # tokenize_pan returns a vault token, or None if the card couldn't be tokenized.
        self._tokenize_pan = tokenize_pan

    def redact(self, text: str) -> Redaction:
        counts: Counter = Counter()

        def placeholder(label: str, value: str):
            def replace(_match: re.Match) -> str:
                counts[label] += 1
                return value
            return replace

        def card(match: re.Match) -> str:
            digits = re.sub(r"[ -]", "", match.group())
            if not luhn_valid(digits):
                counts["number"] += 1
                return "[NUMBER]"
            counts["card"] += 1
            token = self._tokenize_pan(digits) if self._tokenize_pan else None
            return f"[CARD {token}]" if token else "[CARD]"

        # Keyword-anchored patterns first, so "CVV 123" is caught before the digits are judged alone.
        text = CVV.sub(placeholder("cvv", "[CVV]"), text)
        text = EXPIRY.sub(placeholder("expiry", "[EXPIRY]"), text)
        text = PAN_CANDIDATE.sub(card, text)
        text = SSN.sub(placeholder("ssn", "[SSN]"), text)
        text = PHONE.sub(placeholder("phone", "[PHONE]"), text)
        text = EMAIL.sub(placeholder("email", "[EMAIL]"), text)
        text = LONG_NUMBER.sub(placeholder("number", "[NUMBER]"), text)
        return Redaction(text=text, counts=dict(counts))


def assert_no_card_data(text: str) -> None:
    """Fail closed: refuse to send anything that still contains a 13-19 digit run."""
    if PAN_CANDIDATE.search(text):
        raise UnsafePayload("possible card number remained after redaction")

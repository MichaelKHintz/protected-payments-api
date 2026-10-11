"""Phase 3: what the redactor catches, what it leaves alone, and the fail-closed check."""
import pytest

from app.redact import Redactor, UnsafePayload, assert_no_card_data

redactor = Redactor(tokenize_pan=lambda pan: "tok_TESTTESTTESTTESTTEST" + pan[-2:])


@pytest.mark.parametrize("pan", ["4111 1111 1111 1111", "4111-1111-1111-1111", "4111111111111111", "3782 822463 10005"])
def test_card_numbers_become_vault_tokens(pan):
    out = redactor.redact(f"Customer read me {pan} over the phone")
    assert "[CARD tok_" in out.text and out.counts == {"card": 1}
    assert pan not in out.text and pan.replace(" ", "").replace("-", "") not in out.text


def test_non_luhn_long_numbers_are_masked_not_tokenized():
    out = redactor.redact("Order 4111 1111 1111 1112 shipped")
    assert out.text == "Order [NUMBER] shipped"


def test_card_without_tokenizer_still_redacted():
    out = Redactor().redact("card 5555555555554444")
    assert out.text == "card [CARD]"


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("CVV 123", "[CVV]"),
        ("cvc2: 9876", "[CVV]"),
        ("exp 12/27", "[EXPIRY]"),
        ("Expiration date: 01/2029", "[EXPIRY]"),
        ("jane.doe@example.com", "[EMAIL]"),
        ("(512) 555-0142", "[PHONE]"),
        ("+1 512-555-0142", "[PHONE]"),
        ("123-45-6789", "[SSN]"),
        ("routing 021000021", "routing [NUMBER]"),
    ],
)
def test_personal_and_sensitive_data_is_replaced(raw, expected):
    assert redactor.redact(raw).text == expected


def test_ordinary_text_survives():
    text = "Refund $42.10 for order-1001 placed on 2026-10-03, ticket 55821."
    assert redactor.redact(text).text == text


def test_fail_closed_check():
    with pytest.raises(UnsafePayload):
        assert_no_card_data("leftover 4111111111111111")
    assert_no_card_data("[CARD tok_TESTTESTTESTTESTTEST11] and order-1001")

import pytest

from app import cards


@pytest.mark.parametrize("pan", sorted(cards.TEST_CARDS))
def test_every_allowlisted_test_card_passes_luhn(pan):
    assert cards.luhn_valid(pan)


def test_normalize_strips_spaces_and_dashes():
    assert cards.normalize("4111 1111-1111 1111") == "4111111111111111"


@pytest.mark.parametrize("raw", ["4111", "4111a11111111111", "４１１１１１１１１１１１１１１１", "²" * 16])
def test_normalize_rejects_non_ascii_or_wrong_length(raw):
    with pytest.raises(ValueError):
        cards.normalize(raw)


def test_luhn_rejects_a_mistyped_number():
    assert not cards.luhn_valid("4111111111111112")


@pytest.mark.parametrize(
    "pan,expected",
    [("4111111111111111", "visa"), ("5555555555554444", "mastercard"), ("2223003122003222", "mastercard"),
     ("378282246310005", "amex"), ("6011111111111117", "discover")],
)
def test_brand(pan, expected):
    assert cards.brand(pan) == expected

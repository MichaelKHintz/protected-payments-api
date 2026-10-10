"""Card number helpers: normalization, Luhn check, brand detection, and the lab's test-card allowlist."""
import re

# Published test numbers from the card networks and processors. While TEST_CARDS_ONLY=true
# the vault refuses anything else, so a real card number can't end up in the lab by accident.
TEST_CARDS = frozenset({
    "4111111111111111",  # Visa
    "4242424242424242",  # Visa
    "4012888888881881",  # Visa
    "4000056655665556",  # Visa (debit)
    "5555555555554444",  # Mastercard
    "5105105105105100",  # Mastercard
    "2223003122003222",  # Mastercard (2-series)
    "378282246310005",   # American Express
    "371449635398431",   # American Express
    "6011111111111117",  # Discover
    "6011000990139424",  # Discover
})

_SEPARATORS = re.compile(r"[ -]")
# ASCII digits only: str.isdigit() would also accept characters like "²" or Arabic-Indic digits.
_PAN_SHAPE = re.compile(r"[0-9]{13,19}")


def normalize(raw: str) -> str:
    """Strip spaces and dashes and confirm the result looks like a PAN (13-19 ASCII digits)."""
    digits = _SEPARATORS.sub("", raw.strip())
    if not _PAN_SHAPE.fullmatch(digits):
        raise ValueError("card number must be 13-19 digits")
    return digits


def luhn_valid(pan: str) -> bool:
    total = 0
    for i, ch in enumerate(reversed(pan)):
        d = int(ch)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def brand(pan: str) -> str:
    if pan.startswith("4"):
        return "visa"
    if 51 <= int(pan[:2]) <= 55 or 2221 <= int(pan[:4]) <= 2720:
        return "mastercard"
    if pan[:2] in ("34", "37"):
        return "amex"
    if pan.startswith("6011") or pan.startswith("65") or 644 <= int(pan[:3]) <= 649:
        return "discover"
    return "unknown"

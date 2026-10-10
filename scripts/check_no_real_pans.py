#!/usr/bin/env python3
"""pre-commit hook: block any commit containing a card-number-like value that isn't a published test card.

A Luhn-valid 13-19 digit number that isn't on the allowlist below could be a real PAN, and a real PAN
in a public repo is a reportable incident. The hook prints only the first 6 and last 4 digits.
"""
import re
import sys

PUBLISHED_TEST_CARDS = {
    "4111111111111111", "4242424242424242", "4012888888881881", "4000056655665556",
    "4000000000000002",  # processor test number used in the tests as "Luhn-valid but not allowlisted"
    "5555555555554444", "5105105105105100", "2223003122003222",
    "378282246310005", "371449635398431", "6011111111111117", "6011000990139424",
}
CANDIDATE = re.compile(r"(?<!\d)\d(?:[ -]?\d){12,18}(?!\d)")


def luhn_valid(digits: str) -> bool:
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch)
        if i % 2 == 1:
            d = d * 2 - 9 if d > 4 else d * 2
        total += d
    return total % 10 == 0


def main(paths: list[str]) -> int:
    problems = []
    for path in paths:
        try:
            with open(path, encoding="utf-8") as f:
                lines = f.read().splitlines()
        except (UnicodeDecodeError, OSError):
            continue  # binary or unreadable files
        for number, line in enumerate(lines, 1):
            for match in CANDIDATE.finditer(line):
                # \d also matches non-ASCII digits (e.g. fullwidth); normalize so the allowlist still applies.
                digits = "".join(str(int(c)) for c in re.sub(r"[ -]", "", match.group()))
                if luhn_valid(digits) and digits not in PUBLISHED_TEST_CARDS:
                    problems.append(f"{path}:{number}: possible real card number {digits[:6]}...{digits[-4:]}")
    if problems:
        print("\n".join(problems))
        print("Only published test card numbers may be committed. Remove the value or add a reviewed test number.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

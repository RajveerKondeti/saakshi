"""Remove personal identifiers before anything is sent to web search."""
import re

PATTERNS = [
    (r"\b[A-Z]{5}\d{4}[A-Z]\b", "[PAN]"),
    (r"\b\d{2}[A-Z]{5}\d{4}[A-Z][0-9A-Z]Z[0-9A-Z]\b", "[GSTIN]"),
    (r"\b\d{4}\s?\d{4}\s?\d{4}\b", "[AADHAAR]"),
    (r"(\+91[\s-]?)?\b[6-9]\d{9}\b", "[PHONE]"),
    (r"[\w.+-]+@[\w-]+\.[\w.]+", "[EMAIL]"),
    (r"\b\d{9,18}\b", "[NUMBER]"),
]


def redact(text: str) -> str:
    for pattern, label in PATTERNS:
        text = re.sub(pattern, label, text)
    return text

"""PHI-like pattern detection for the no-storage prototype."""

from __future__ import annotations

import re
from typing import List, Tuple


PHI_PATTERNS: Tuple[Tuple[str, str], ...] = (
    ("email address", r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b"),
    ("phone number", r"\b(?:\+?\d{1,3}[-.\s]?)?(?:\(?\d{3,4}\)?[-.\s]?)\d{3}[-.\s]?\d{4}\b"),
    ("medical record or hospital number", r"\b(?:MRN|NHS|hospital\s*no\.?|patient\s+id\b)\s*[:#-]?\s*[A-Z0-9-]{5,}\b"),
    ("full date", r"\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}[/-]\d{1,2}[/-]\d{1,2})\b"),
    ("street address", r"\b\d{1,5}\s+[A-Z][A-Za-z0-9.'-]*(?:\s+[A-Z][A-Za-z0-9.'-]*){0,4}\s+(?:Street|St|Road|Rd|Avenue|Ave|Lane|Ln|Drive|Dr|Way)\b"),
    ("explicit patient name", r"\b(?:patient\s+name|name)\s*[:=-]\s*[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b"),
)


def detect_phi_warnings(text: str) -> List[str]:
    """Return human-readable warnings for PHI-like content.

    This is intentionally conservative and transparent. It is not a de-identification
    system; it just nudges clinicians away from entering identifiable case text.
    """
    if not text:
        return []

    warnings: List[str] = []
    for label, pattern in PHI_PATTERNS:
        if re.search(pattern, text, flags=re.IGNORECASE):
            warnings.append(f"Possible {label} detected. Remove identifiers before using the prototype.")

    # Catch common prose forms such as "John Smith, 54M..." only when introduced
    # as a patient, not every capitalized phrase in a clinical note.
    if re.search(r"\b(?:patient|pt)\s+(?:is\s+)?[A-Z][a-z]+\s+[A-Z][a-z]+\b", text):
        warnings.append("Possible patient name detected. Use de-identified descriptions only.")

    return list(dict.fromkeys(warnings))

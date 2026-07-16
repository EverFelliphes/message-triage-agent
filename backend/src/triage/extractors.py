"""Deterministic, rule-based extraction (BE-04).

This module is intentionally free of any LLM dependency: it is the *physical*
evidence of rule/AI separation for the audit story. The classifier's merge layer
lets these deterministic results override the model on regulated fields.
"""

from __future__ import annotations

import re
from datetime import date, timedelta

from .schemas import Urgencia

# --- CNPJ ------------------------------------------------------------------

# Matches CNPJ with or without punctuation: 00.000.000/0000-00 or 00000000000000
_CNPJ_RE = re.compile(r"\b(\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2})\b")
# First/second check-digit weights (Receita Federal, modulo 11).
_DV1_WEIGHTS = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
_DV2_WEIGHTS = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]


def _dv(digits: str, weights: list[int]) -> int:
    """Compute a single CNPJ check digit via modulo 11."""
    total = sum(int(d) * w for d, w in zip(digits, weights, strict=True))
    rem = total % 11
    return 0 if rem < 2 else 11 - rem


def validate_cnpj(cnpj: str) -> bool:
    """Validate a CNPJ by its two check digits (modulo 11).

    Rule source: Receita Federal do Brasil, CNPJ check-digit algorithm.
    """
    digits = re.sub(r"\D", "", cnpj)
    if len(digits) != 14 or digits == digits[0] * 14:
        return False
    return _dv(digits[:12], _DV1_WEIGHTS) == int(digits[12]) and _dv(
        digits[:13], _DV2_WEIGHTS
    ) == int(digits[13])


def _format_cnpj(digits: str) -> str:
    """Normalize 14 raw digits to ``XX.XXX.XXX/XXXX-XX``."""
    return f"{digits[:2]}.{digits[2:5]}.{digits[5:8]}/{digits[8:12]}-{digits[12:]}"


def extract_cnpj(text: str) -> str | None:
    """Return the first *valid* CNPJ found in ``text``, normalized, or ``None``.

    A malformed candidate that fails DV validation returns ``None`` — we never
    surface an unverified document number on a regulated field.
    """
    for match in _CNPJ_RE.finditer(text):
        digits = re.sub(r"\D", "", match.group(1))
        if len(digits) == 14 and validate_cnpj(digits):
            return _format_cnpj(digits)
    return None


# --- Dates -----------------------------------------------------------------

_DATE_RE = re.compile(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})\b")
_RELATIVE = {"hoje": 0, "amanhã": 1, "amanha": 1, "ontem": -1}


def extract_dates(text: str, *, today: date | None = None) -> list[date]:
    """Extract BR-format and relative dates, deduplicated, in order of appearance.

    Supports ``dd/mm/yyyy``, ``dd-mm-yyyy``, ``dd/mm/yy`` and the relative words
    ``hoje``/``amanhã``/``ontem``. ``today`` is injectable for deterministic tests.
    """
    today = today or date.today()
    found: list[date] = []

    def _add(d: date) -> None:
        if d not in found:
            found.append(d)

    for day_s, month_s, year_s in _DATE_RE.findall(text):
        day, month, year = int(day_s), int(month_s), int(year_s)
        if year < 100:  # two-digit year → 2000s
            year += 2000
        try:
            _add(date(year, month, day))
        except ValueError:
            continue  # impossible calendar date (e.g. 31/02) — skip

    lowered = text.lower()
    for word, offset in _RELATIVE.items():
        if re.search(rf"\b{re.escape(word)}\b", lowered):
            _add(today + timedelta(days=offset))

    return found


# --- Urgency ---------------------------------------------------------------

_HIGH_URGENCY = re.compile(
    r"\b(urgent[ea]|urgência|urgencia|asap|imediat[oa]|hoje|prazo)\b", re.IGNORECASE
)
_MEDIUM_URGENCY = re.compile(r"(assim que poss[íi]vel|em breve|\bbreve\b|\blogo\b)", re.IGNORECASE)


def detect_urgency(text: str) -> Urgencia:
    """Classify urgency by case-insensitive keyword matching. Default: low."""
    if _HIGH_URGENCY.search(text):
        return Urgencia.ALTA
    if _MEDIUM_URGENCY.search(text):
        return Urgencia.MEDIA
    return Urgencia.BAIXA

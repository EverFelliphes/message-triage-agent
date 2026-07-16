from datetime import date

from triage.extractors import detect_urgency, extract_cnpj, extract_dates, validate_cnpj
from triage.schemas import Urgencia


class TestCnpj:
    def test_valid_formatted(self):
        assert extract_cnpj("empresa 45.723.174/0001-10 aqui") == "45.723.174/0001-10"

    def test_valid_unformatted_is_normalized(self):
        assert extract_cnpj("cnpj 45723174000110") == "45.723.174/0001-10"

    def test_invalid_check_digit_returns_none(self):
        assert extract_cnpj("cnpj 45.723.174/0001-99") is None

    def test_missing_returns_none(self):
        assert extract_cnpj("sem documento aqui") is None

    def test_repeated_digits_rejected(self):
        assert validate_cnpj("00000000000000") is False

    def test_validate_helper(self):
        assert validate_cnpj("45.723.174/0001-10") is True


class TestDates:
    def test_multiple_formats(self):
        dates = extract_dates("vence 10/08/2026 e também 05-01-2025")
        assert date(2026, 8, 10) in dates
        assert date(2025, 1, 5) in dates

    def test_two_digit_year(self):
        assert date(2026, 7, 1) in extract_dates("data 01/07/26")

    def test_relative_words(self):
        today = date(2026, 7, 16)
        dates = extract_dates("mandei ontem e volto amanhã", today=today)
        assert date(2026, 7, 15) in dates
        assert date(2026, 7, 17) in dates

    def test_dedup_and_invalid_skipped(self):
        dates = extract_dates("10/08/2026 10/08/2026 31/02/2026")
        assert dates.count(date(2026, 8, 10)) == 1


class TestUrgency:
    def test_high(self):
        assert detect_urgency("Isso é URGENTE, preciso hoje") == Urgencia.ALTA

    def test_medium(self):
        assert detect_urgency("me responda assim que possível") == Urgencia.MEDIA

    def test_low_default(self):
        assert detect_urgency("bom dia, tudo bem?") == Urgencia.BAIXA

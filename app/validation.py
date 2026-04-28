from __future__ import annotations

import re
from datetime import datetime, timezone

ALLOWED_SURVEY_PERIODICITIES = {"Annual", "Quarterly", "Monthly", "Other"}
ASHE_SURVEY_CODE = "141"
NI_NUMBER_PATTERN = re.compile(r"^[A-Z]{2}\d{6}[A-Z]$")


def month_allowed_for_periodicity(
    survey_code: str, periodicity: str, month: int
) -> bool:
    # Explicit business exception for survey 141.
    if survey_code == "141":
        return month == 4

    if periodicity == "Monthly":
        return 1 <= month <= 12
    if periodicity == "Quarterly":
        return month in {3, 6, 9, 12}
    if periodicity in {"Annual", "Other"}:
        return month == 12
    return False


def is_period_allowed_for_survey(
    survey_code: str, periodicity: str, period: str
) -> bool:
    if not is_valid_period(period):
        return False

    month = int(period[4:6])
    return month_allowed_for_periodicity(survey_code, periodicity, month)


def is_valid_ruref(value: str) -> bool:
    return len(value) == 11 and value.isdigit()


def is_valid_period(value: str) -> bool:
    if len(value) != 6 or not value.isdigit():
        return False

    year = int(value[:4])
    month = int(value[4:])
    if month < 1 or month > 12:
        return False

    current_year = datetime.now(timezone.utc).year
    return 1990 <= year <= current_year + 5


def is_valid_survey_periodicity(value: str) -> bool:
    return value in ALLOWED_SURVEY_PERIODICITIES


def normalize_reference(value: str) -> str:
    return "".join(value.split()).upper()


def is_valid_ni_number(value: str) -> bool:
    normalized_value = normalize_reference(value)
    if not NI_NUMBER_PATTERN.fullmatch(normalized_value):
        return False

    return normalized_value[6:8] == "14"


def is_valid_reference(value: str) -> bool:
    normalized_value = normalize_reference(value)
    return is_valid_ruref(normalized_value) or is_valid_ni_number(normalized_value)


def is_valid_reference_for_survey(value: str, survey_code: str | None) -> bool:
    normalized_value = normalize_reference(value)
    if survey_code == ASHE_SURVEY_CODE:
        return is_valid_ni_number(normalized_value)

    return is_valid_ruref(normalized_value)

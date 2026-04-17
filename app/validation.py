from __future__ import annotations

from datetime import datetime, timezone


ALLOWED_SURVEY_PERIODICITIES = {"Annual", "Quarterly", "Monthly", "Other"}


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

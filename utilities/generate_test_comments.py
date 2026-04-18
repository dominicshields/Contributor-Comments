from __future__ import annotations

import argparse
import csv
import random
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
import os

from faker import Faker
from sqlalchemy import create_engine, text


DEFAULT_DATABASE_URL = "postgresql+psycopg://postgres:postgres@localhost:5432/contributor_comments"
DEFAULT_OUTPUT_FILENAME = "synthetic_test_comments.csv"
ALLOWED_PERIODICITIES = {"Annual", "Quarterly", "Monthly", "Other"}
CHEMICAL_ELEMENTS = [
    "Hydrogen",
    "Helium",
    "Lithium",
    "Beryllium",
    "Boron",
    "Carbon",
    "Nitrogen",
    "Oxygen",
    "Fluorine",
    "Neon",
    "Sodium",
    "Magnesium",
    "Aluminium",
    "Silicon",
    "Phosphorus",
    "Sulfur",
    "Chlorine",
    "Argon",
    "Potassium",
    "Calcium",
    "Iron",
    "Nickel",
    "Copper",
    "Zinc",
    "Silver",
    "Tin",
    "Gold",
    "Mercury",
    "Lead",
    "Uranium",
]


@dataclass(frozen=True)
class SurveyMetadata:
    code: str
    periodicity: str


@dataclass
class RurefState:
    survey_history: list[tuple[str, str]]
    should_emit_general: bool
    emitted_general: bool


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate synthetic test comments based on survey metadata periodicity rules."
    )
    parser.add_argument(
        "comment_count",
        type=int,
        help="Number of synthetic comments to generate.",
    )
    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT_FILENAME,
        help=f"Output CSV file path (default: {DEFAULT_OUTPUT_FILENAME}).",
    )
    return parser.parse_args()


def first_day_of_month(year: int, month: int) -> datetime:
    return datetime(year, month, 1, 0, 0, 0)


def first_day_next_month(year: int, month: int) -> datetime:
    if month == 12:
        return datetime(year + 1, 1, 1, 0, 0, 0)
    return datetime(year, month + 1, 1, 0, 0, 0)


def add_year(year: int, month: int) -> datetime:
    return datetime(year + 1, month, 1, 0, 0, 0)


def month_allowed_for_periodicity(survey_code: str, periodicity: str, month: int) -> bool:
    if survey_code == "141":
        return month == 4

    if periodicity == "Monthly":
        return 1 <= month <= 12
    if periodicity == "Quarterly":
        return month in {3, 6, 9, 12}
    if periodicity in {"Annual", "Other"}:
        return month == 12
    return False


def build_valid_periods(survey_code: str, periodicity: str) -> list[str]:
    periods: list[str] = []
    for year in range(2020, 2026):
        for month in range(1, 13):
            if month_allowed_for_periodicity(survey_code, periodicity, month):
                periods.append(f"{year}{month:02d}")
    return periods


def random_saved_datetime_for_period(period: str) -> datetime:
    year = int(period[:4])
    month = int(period[4:6])

    # Saved date must be after the period month and less than one year later.
    start = first_day_next_month(year, month)
    end_exclusive = add_year(year, month)

    max_seconds = int((end_exclusive - start).total_seconds())
    offset_seconds = random.randint(0, max_seconds - 1)
    return start + timedelta(seconds=offset_seconds)


def load_survey_metadata(database_url: str) -> list[SurveyMetadata]:
    engine = create_engine(database_url)
    surveys: list[SurveyMetadata] = []

    with engine.connect() as connection:
        result = connection.execute(
            text(
                """
                SELECT code, periodicity
                FROM surveys
                ORDER BY display_order ASC
                """
            )
        )

        for row in result:
            code = str(row.code).strip()
            periodicity = str(row.periodicity or "").strip()
            if periodicity not in ALLOWED_PERIODICITIES:
                periodicity = "Other"
            surveys.append(SurveyMetadata(code=code, periodicity=periodicity))

    if not surveys:
        raise RuntimeError("No surveys found in survey metadata.")

    return surveys


def build_author_pool(fake: Faker, max_names: int = 100) -> list[str]:
    names: set[str] = set()
    while len(names) < max_names:
        names.add(fake.name())
    return sorted(names)


def attach_contact_details(records: list[dict[str, str]], fake: Faker) -> None:
    for record in records:
        record["contact_name"] = ""
        record["contact_phone"] = ""
        record["contact_email"] = ""

    if not records:
        return

    target_contact_rows = len(records) // 3
    if target_contact_rows == 0:
        return

    first_record_index_by_contact_scope: dict[tuple[str, str], int] = {}
    for index, record in enumerate(records):
        contact_scope = (record["ruref"], record["survey_code"])
        if contact_scope not in first_record_index_by_contact_scope:
            first_record_index_by_contact_scope[contact_scope] = index

    unique_scopes = list(first_record_index_by_contact_scope.keys())
    random.shuffle(unique_scopes)
    selected_scopes = unique_scopes[: min(target_contact_rows, len(unique_scopes))]

    for scope in selected_scopes:
        record_index = first_record_index_by_contact_scope[scope]
        record = records[record_index]
        record["contact_name"] = fake.name()
        record["contact_phone"] = fake.phone_number()
        record["contact_email"] = fake.email()


def generate_comments(comment_count: int, surveys: list[SurveyMetadata]) -> list[dict[str, str]]:
    if comment_count < 0:
        raise ValueError("comment_count must be zero or greater")

    fake = Faker("en_GB")
    authors = build_author_pool(fake, max_names=100)
    period_map = {
        survey.code: build_valid_periods(survey.code, survey.periodicity)
        for survey in surveys
    }
    ruref_states: dict[str, RurefState] = {}
    general_periods = [f"{year}{month:02d}" for year in range(2020, 2026) for month in range(1, 13)]
    new_ruref_count = 0

    def choose_period(code: str, avoid_period: str | None = None) -> str | None:
        valid_periods = period_map.get(code, [])
        if not valid_periods:
            return None
        if avoid_period is None:
            return random.choice(valid_periods)

        alternatives = [period for period in valid_periods if period != avoid_period]
        if alternatives:
            return random.choice(alternatives)
        return random.choice(valid_periods)

    records: list[dict[str, str]] = []
    for index in range(1, comment_count + 1):
        use_existing_ruref = bool(ruref_states) and random.random() < 0.5

        if use_existing_ruref:
            ruref = random.choice(list(ruref_states.keys()))
        else:
            ruref = fake.numerify(text="###########")
            new_ruref_count += 1
            ruref_states[ruref] = RurefState(
                survey_history=[],
                should_emit_general=(new_ruref_count % 5 == 0),
                emitted_general=False,
            )

        ruref_state = ruref_states[ruref]
        emit_general_comment = ruref_state.should_emit_general and not ruref_state.emitted_general

        if emit_general_comment:
            survey_code = ""
            period = random.choice(general_periods)
            ruref_state.emitted_general = True
        else:
            if ruref_state.survey_history:
                last_survey_code, last_period = ruref_state.survey_history[-1]

                keep_same_survey = random.random() < 0.1
                if keep_same_survey:
                    survey_code = last_survey_code
                else:
                    candidate_codes = [survey.code for survey in surveys if survey.code != last_survey_code]
                    if candidate_codes:
                        survey_code = random.choice(candidate_codes)
                    else:
                        survey_code = last_survey_code

                period = choose_period(survey_code, avoid_period=last_period)
                if period is None:
                    continue
            else:
                survey = random.choice(surveys)
                survey_code = survey.code
                period = choose_period(survey_code)
                if period is None:
                    continue

        spoke_to = fake.name()
        comment_text = f"Spoke to {spoke_to} they said {fake.sentence(nb_words=14)}"
        if index % 10 == 0:
            comment_text = f"{comment_text} {random.choice(CHEMICAL_ELEMENTS)}"
        saved_at = random_saved_datetime_for_period(period)

        records.append(
            {
                "ruref": ruref,
                "survey_code": survey_code,
                "period": period,
                "comment_text": comment_text,
                "saved_at": saved_at.strftime("%Y-%m-%d %H:%M:%S"),
                "author_name": random.choice(authors),
                "is_general": "1" if emit_general_comment else "0",
            }
        )

        if survey_code:
            ruref_state.survey_history.append((survey_code, period))

    attach_contact_details(records, fake)

    return records


def write_output(records: list[dict[str, str]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "ruref",
        "survey_code",
        "period",
        "comment_text",
        "saved_at",
        "author_name",
        "is_general",
        "contact_name",
        "contact_phone",
        "contact_email",
    ]

    with output_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)


def main() -> None:
    args = parse_args()
    output_path = Path(args.output).resolve()

    database_url = os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)
    surveys = load_survey_metadata(database_url)
    records = generate_comments(args.comment_count, surveys)
    write_output(records, output_path)

    print(f"Generated {len(records)} comments at {output_path}")


if __name__ == "__main__":
    main()

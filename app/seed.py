from __future__ import annotations

from .extensions import db
from .models import Survey, User
from .validation import is_valid_survey_periodicity


DEFAULT_SURVEYS = ["221", "241", "002", "023", "138"]

DEFAULT_SURVEY_METADATA = {
    "221": {"description": "Survey 221", "periodicity": "Monthly", "forms_per_period": 0},
    "241": {"description": "Survey 241", "periodicity": "Monthly", "forms_per_period": 0},
    "002": {"description": "Survey 002", "periodicity": "Monthly", "forms_per_period": 0},
    "023": {"description": "Survey 023", "periodicity": "Monthly", "forms_per_period": 0},
    "138": {"description": "Survey 138", "periodicity": "Monthly", "forms_per_period": 0},
}


TEST_USERS = [
    {"username": "admin", "full_name": "Admin User", "password": "Password123!", "is_admin": True},
    {"username": "analyst1", "full_name": "Analyst One", "password": "Password123!", "is_admin": False},
    {"username": "analyst2", "full_name": "Analyst Two", "password": "Password123!", "is_admin": False},
]


def seed_reference_data() -> None:
    for index, code in enumerate(DEFAULT_SURVEYS, start=1):
        survey_metadata = DEFAULT_SURVEY_METADATA[code]
        existing = db.session.get(Survey, code)
        if existing is None:
            db.session.add(
                Survey(
                    code=code,
                    display_order=index,
                    description=survey_metadata["description"],
                    periodicity=survey_metadata["periodicity"],
                    forms_per_period=survey_metadata["forms_per_period"],
                    is_active=True,
                )
            )
            continue

        if existing.is_active is False:
            existing.is_active = True
        if not existing.description:
            existing.description = survey_metadata["description"]
        if not existing.periodicity or not is_valid_survey_periodicity(existing.periodicity):
            # Keep seeded periodicity values within the allowed set.
            existing.periodicity = survey_metadata["periodicity"]

    for user_data in TEST_USERS:
        existing_user = User.query.filter_by(username=user_data["username"]).first()
        if existing_user is not None:
            continue

        user = User(
            username=user_data["username"],
            full_name=user_data["full_name"],
            is_admin=user_data["is_admin"],
        )
        user.set_password(user_data["password"])
        db.session.add(user)

    db.session.commit()

from __future__ import annotations

import csv
import io
from pathlib import Path
import re
import secrets
from datetime import UTC, datetime
from time import perf_counter

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from werkzeug.security import generate_password_hash

from ..extensions import db
from ..models import Comment, CommentEdit, ReportingUnit, Survey, User
from ..validation import ALLOWED_SURVEY_PERIODICITIES, is_valid_period, is_valid_ruref, is_valid_survey_periodicity


bp = Blueprint("admin", __name__, url_prefix="/admin")

SURVEYS_CSV_PATH = Path(__file__).resolve().parents[2] / "surveys.csv"
PERIODICITY_ALLOWED_MONTHS = {
    "Monthly": {1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12},
    "Quarterly": {3, 6, 9, 12},
    "Annual": {12},
    "Other": {12},
}


def _parse_forms_per_period(value: str | None) -> int:
    if value is None:
        return 0

    raw = value.strip()
    if raw == "":
        return 0

    try:
        parsed = int(raw)
    except ValueError:
        return 0

    return parsed if parsed >= 0 else 0


def _month_allowed_for_survey(survey_code: str, periodicity: str, month: int) -> bool:
    # Explicit business exception for survey 141.
    if survey_code == "141":
        return month == 4

    allowed_months = PERIODICITY_ALLOWED_MONTHS.get(periodicity)
    if allowed_months is None:
        return False
    return month in allowed_months


def _is_period_allowed_for_survey(survey: Survey, period: str) -> bool:
    if not is_valid_period(period):
        return False

    month = int(period[4:6])
    return _month_allowed_for_survey(survey.code, survey.periodicity, month)


def _parse_saved_at(value: str | None) -> datetime | None:
    if value is None:
        return None

    raw = value.strip()
    if not raw:
        return None

    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            parsed = datetime.strptime(raw, fmt)
            return parsed.replace(tzinfo=UTC)
        except ValueError:
            continue

    return None


def _username_from_full_name(full_name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", ".", full_name.strip().lower()).strip(".")
    if not base:
        base = "bulk.user"
    return base[:60]


def _resolve_author(author_name: str, fallback_user: User) -> User:
    if not author_name.strip():
        return fallback_user

    existing = User.query.filter_by(full_name=author_name.strip()).first()
    if existing is not None:
        return existing

    base_username = _username_from_full_name(author_name)
    username = base_username
    suffix = 1
    while User.query.filter_by(username=username).first() is not None:
        username = f"{base_username}.{suffix}"
        suffix += 1

    user = User(
        username=username,
        full_name=author_name.strip(),
        is_admin=False,
        password_hash=generate_password_hash(secrets.token_urlsafe(24)),
    )
    db.session.add(user)
    db.session.flush()
    return user


def _ensure_admin():
    if not current_user.is_admin:
        flash("Admin access required.", "error")
        return False
    return True


@bp.get("/surveys")
@login_required
def surveys():
    all_surveys = Survey.query.order_by(Survey.code.asc()).all()
    return render_template("admin/surveys.html", surveys=all_surveys)


@bp.post("/surveys")
@login_required
def add_survey():
    if not _ensure_admin():
        return redirect(url_for("comments.index"))

    code = request.form.get("code", "").strip()
    description = request.form.get("description", "").strip()
    periodicity = request.form.get("periodicity", "").strip()
    forms_per_period_raw = request.form.get("forms_per_period", "").strip()
    if len(code) != 3 or not code.isdigit():
        flash("Survey code must be exactly 3 numeric characters.", "error")
        return redirect(url_for("admin.surveys"))

    if db.session.get(Survey, code) is not None:
        flash("Survey code already exists.", "error")
        return redirect(url_for("admin.surveys"))

    try:
        forms_per_period = int(forms_per_period_raw)
    except ValueError:
        flash("Forms per period must be a whole number.", "error")
        return redirect(url_for("admin.surveys"))

    if forms_per_period < 0:
        flash("Forms per period must be zero or greater.", "error")
        return redirect(url_for("admin.surveys"))

    if not description:
        flash("Survey description is required.", "error")
        return redirect(url_for("admin.surveys"))

    if not periodicity:
        flash("Survey periodicity is required.", "error")
        return redirect(url_for("admin.surveys"))

    if not is_valid_survey_periodicity(periodicity):
        flash(
            f"Survey periodicity must be one of: {', '.join(sorted(ALLOWED_SURVEY_PERIODICITIES))}.",
            "error",
        )
        return redirect(url_for("admin.surveys"))

    max_order = db.session.query(db.func.max(Survey.display_order)).scalar() or 0
    db.session.add(
        Survey(
            code=code,
            display_order=max_order + 1,
            description=description,
            periodicity=periodicity,
            forms_per_period=forms_per_period,
            is_active=True,
        )
    )
    db.session.commit()
    flash("Survey code added.", "success")
    return redirect(url_for("admin.surveys"))


@bp.post("/surveys/<code>/metadata")
@login_required
def update_survey_metadata(code: str):
    if not _ensure_admin():
        return redirect(url_for("comments.index"))

    survey = db.session.get(Survey, code)
    if survey is None:
        flash("Survey not found.", "error")
        return redirect(url_for("admin.surveys"))

    description = request.form.get("description", "").strip()
    periodicity = request.form.get("periodicity", "").strip()
    forms_per_period_raw = request.form.get("forms_per_period", "").strip()

    if not description:
        flash("Survey description is required.", "error")
        return redirect(url_for("admin.surveys"))

    if not periodicity:
        flash("Survey periodicity is required.", "error")
        return redirect(url_for("admin.surveys"))

    if not is_valid_survey_periodicity(periodicity):
        flash(
            f"Survey periodicity must be one of: {', '.join(sorted(ALLOWED_SURVEY_PERIODICITIES))}.",
            "error",
        )
        return redirect(url_for("admin.surveys"))

    try:
        forms_per_period = int(forms_per_period_raw)
    except ValueError:
        flash("Forms per period must be a whole number.", "error")
        return redirect(url_for("admin.surveys"))

    if forms_per_period < 0:
        flash("Forms per period must be zero or greater.", "error")
        return redirect(url_for("admin.surveys"))

    survey.description = description
    survey.periodicity = periodicity
    survey.forms_per_period = forms_per_period
    db.session.commit()
    flash(f"Survey {survey.code} metadata updated.", "success")
    return redirect(url_for("admin.surveys"))


@bp.post("/surveys/<code>/toggle-active")
@login_required
def toggle_survey_active(code: str):
    if not _ensure_admin():
        return redirect(url_for("comments.index"))

    survey = db.session.get(Survey, code)
    if survey is None:
        flash("Survey not found.", "error")
        return redirect(url_for("admin.surveys"))

    survey.is_active = not survey.is_active
    db.session.commit()
    state = "activated" if survey.is_active else "deactivated"
    flash(f"Survey {survey.code} {state}.", "success")
    return redirect(url_for("admin.surveys"))


@bp.post("/surveys/<code>/delete")
@login_required
def delete_survey(code: str):
    if not _ensure_admin():
        return redirect(url_for("comments.index"))

    survey = db.session.get(Survey, code)
    if survey is None:
        flash("Survey not found.", "error")
        return redirect(url_for("admin.surveys"))

    comment_ids = [
        comment_id
        for (comment_id,) in db.session.query(Comment.id).filter(Comment.survey_code == code).all()
    ]

    deleted_comments = 0
    if comment_ids:
        CommentEdit.query.filter(CommentEdit.comment_id.in_(comment_ids)).delete(synchronize_session=False)
        deleted_comments = Comment.query.filter(Comment.survey_code == code).delete(synchronize_session=False)

    db.session.delete(survey)
    db.session.commit()
    flash(f"Survey {code} deleted completely. Removed {deleted_comments} related comments.", "success")
    return redirect(url_for("admin.surveys"))


@bp.post("/surveys/import")
@login_required
def import_surveys():
    if not _ensure_admin():
        return redirect(url_for("comments.index"))

    if not SURVEYS_CSV_PATH.exists():
        flash("surveys.csv file was not found at the repository root.", "error")
        return redirect(url_for("admin.surveys"))

    created = 0
    updated = 0
    skipped = 0
    max_order = db.session.query(db.func.max(Survey.display_order)).scalar() or 0

    with SURVEYS_CSV_PATH.open("r", encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        for row in reader:
            code = (row.get("Survey") or "").strip()
            description = (row.get("Description") or "").strip()
            periodicity = (row.get("Periodicity") or "").strip()
            forms_per_period = _parse_forms_per_period(row.get("Forms_per_period"))

            if len(code) != 3 or not code.isdigit():
                skipped += 1
                continue

            if not description:
                description = f"Survey {code}"

            if not is_valid_survey_periodicity(periodicity):
                periodicity = "Other"

            survey = db.session.get(Survey, code)
            if survey is None:
                max_order += 1
                db.session.add(
                    Survey(
                        code=code,
                        display_order=max_order,
                        description=description,
                        periodicity=periodicity,
                        forms_per_period=forms_per_period,
                        is_active=True,
                    )
                )
                created += 1
                continue

            survey.description = description
            survey.periodicity = periodicity
            survey.forms_per_period = forms_per_period
            updated += 1

    db.session.commit()
    flash(
        f"Surveys import complete. Created: {created}, Updated: {updated}, Skipped: {skipped}.",
        "success",
    )
    return redirect(url_for("admin.surveys"))


@bp.get("/system-config/bulk-upload-comments")
@login_required
def bulk_upload_comments():
    if not _ensure_admin():
        return redirect(url_for("comments.index"))

    return render_template("admin/bulk_upload_comments.html")


@bp.post("/system-config/bulk-upload-comments")
@login_required
def bulk_upload_comments_submit():
    if not _ensure_admin():
        return redirect(url_for("comments.index"))

    upload = request.files.get("comments_file")
    if upload is None or not upload.filename:
        flash("Please choose a CSV file to upload.", "error")
        return redirect(url_for("admin.bulk_upload_comments"))

    try:
        content = upload.stream.read().decode("utf-8-sig")
    except UnicodeDecodeError:
        flash("Unable to read file. Please upload a UTF-8 encoded CSV.", "error")
        return redirect(url_for("admin.bulk_upload_comments"))

    reader = csv.DictReader(io.StringIO(content))
    required_columns = {"ruref", "survey_code", "period", "comment_text"}
    columns = {column.strip().lower() for column in (reader.fieldnames or [])}
    if not required_columns.issubset(columns):
        flash(
            "CSV must include columns: ruref, survey_code, period, comment_text.",
            "error",
        )
        return redirect(url_for("admin.bulk_upload_comments"))

    created = 0
    skipped = 0
    started_at = perf_counter()

    for row in reader:
        row_normalized = {str(k).strip().lower(): (v or "").strip() for k, v in row.items()}

        ruref = row_normalized.get("ruref", "")
        survey_code = row_normalized.get("survey_code", "")
        period = row_normalized.get("period", "")
        comment_text = row_normalized.get("comment_text", "")
        author_name = row_normalized.get("author_name", "")
        saved_at = _parse_saved_at(row_normalized.get("saved_at", ""))

        if not is_valid_ruref(ruref) or not comment_text:
            skipped += 1
            continue

        survey = db.session.get(Survey, survey_code)
        if survey is None or not survey.is_active:
            skipped += 1
            continue

        if not _is_period_allowed_for_survey(survey, period):
            skipped += 1
            continue

        reporting_unit = db.session.get(ReportingUnit, ruref)
        if reporting_unit is None:
            reporting_unit = ReportingUnit(ruref=ruref)
            db.session.add(reporting_unit)

        author = _resolve_author(author_name, current_user)

        comment = Comment(
            ruref=ruref,
            survey_code=survey_code,
            period=period,
            comment_text=comment_text,
            author_id=author.id,
        )
        if saved_at is not None:
            comment.created_at = saved_at
            comment.updated_at = saved_at

        db.session.add(comment)
        created += 1

    db.session.commit()
    elapsed_seconds = perf_counter() - started_at
    flash(
        f"Bulk upload complete. Added {created} comments in {elapsed_seconds:.2f} seconds. Skipped: {skipped}.",
        "success",
    )
    return redirect(url_for("admin.bulk_upload_comments"))


@bp.get("/system-config/delete-all-comments")
@login_required
def delete_all_comments_page():
    if not _ensure_admin():
        return redirect(url_for("comments.index"))

    comment_count = db.session.query(db.func.count(Comment.id)).scalar() or 0
    return render_template("admin/delete_all_comments.html", comment_count=comment_count)


@bp.post("/system-config/delete-all-comments")
@login_required
def delete_all_comments_submit():
    if not _ensure_admin():
        return redirect(url_for("comments.index"))

    deleted_edits = CommentEdit.query.delete(synchronize_session=False)
    deleted_comments = Comment.query.delete(synchronize_session=False)
    db.session.commit()

    flash(
        f"All comments deleted. Removed {deleted_comments} comments and {deleted_edits} comment edits.",
        "success",
    )
    return redirect(url_for("admin.delete_all_comments_page"))



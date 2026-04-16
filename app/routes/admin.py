from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ..extensions import db
from ..models import Comment, CommentEdit, Survey


bp = Blueprint("admin", __name__, url_prefix="/admin")


def _ensure_admin():
    if not current_user.is_admin:
        flash("Admin access required.", "error")
        return False
    return True


@bp.get("/surveys")
@login_required
def surveys():
    if not _ensure_admin():
        return redirect(url_for("comments.index"))

    all_surveys = Survey.query.order_by(Survey.code.asc()).all()
    return render_template("admin/surveys.html", surveys=all_surveys)


@bp.post("/surveys")
@login_required
def add_survey():
    if not _ensure_admin():
        return redirect(url_for("comments.index"))

    code = request.form.get("code", "").strip()
    description = request.form.get("description", "").strip()
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

    max_order = db.session.query(db.func.max(Survey.display_order)).scalar() or 0
    db.session.add(
        Survey(
            code=code,
            display_order=max_order + 1,
            description=description,
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
    forms_per_period_raw = request.form.get("forms_per_period", "").strip()

    if not description:
        flash("Survey description is required.", "error")
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



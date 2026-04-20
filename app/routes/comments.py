from __future__ import annotations

import calendar
from collections import OrderedDict
from typing import Optional

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import distinct, or_

from ..extensions import db
from ..models import Comment, CommentEdit, Contact, ReportingUnit, Survey, User
from ..validation import is_period_allowed_for_survey, is_valid_period, is_valid_ruref

bp = Blueprint("comments", __name__)
GENERAL_GROUP_KEY = "General"


def _query_flag(name: str, default: bool = False) -> bool:
    values = request.args.getlist(name)
    if not values:
        return default

    raw = values[-1].strip().lower()
    return raw in {"1", "true", "yes", "on", "y"}


def _add_comment_form_state(source) -> dict[str, str]:
    is_general = source.get("is_general") == "1"
    return {
        "tab": "add",
        "add_ruref": source.get("ruref", "").strip(),
        "add_survey": "" if is_general else source.get("survey", "").strip(),
        "add_period": source.get("period", "").strip(),
        "add_comment": source.get("comment", "").strip(),
        "add_is_general": "1" if is_general else "0",
        "add_contact_name": source.get("contact_name", "").strip(),
        "add_contact_phone": source.get("contact_phone", "").strip(),
        "add_contact_email": source.get("contact_email", "").strip(),
    }


def _add_comment_return_state(source) -> dict[str, str]:
    return {
        "tab": "add",
        "add_ruref": source.get("add_ruref", "").strip(),
        "add_survey": source.get("add_survey", "").strip(),
        "add_period": source.get("add_period", "").strip(),
        "add_comment": source.get("add_comment", "").strip(),
        "add_is_general": "1" if source.get("add_is_general") == "1" else "0",
        "add_contact_name": source.get("add_contact_name", "").strip(),
        "add_contact_phone": source.get("add_contact_phone", "").strip(),
        "add_contact_email": source.get("add_contact_email", "").strip(),
    }


def _has_add_comment_return_state(state: dict[str, str]) -> bool:
    return (
        any(
            state[key]
            for key in (
                "add_ruref",
                "add_survey",
                "add_period",
                "add_comment",
                "add_contact_name",
                "add_contact_phone",
                "add_contact_email",
            )
        )
        or state.get("add_is_general") == "1"
    )


def _format_count_for_display(value: int) -> str:
    return f"{value:,}".replace(",", " ")


def _survey_order_map() -> dict[str, int]:
    surveys = Survey.query.order_by(Survey.display_order.asc()).all()
    return {survey.code: survey.display_order for survey in surveys}


def _group_comments(comments: list[Comment]) -> OrderedDict[str, list[Comment]]:
    ordered = OrderedDict()
    ordered[GENERAL_GROUP_KEY] = []
    surveys = Survey.query.order_by(Survey.display_order.asc()).all()
    for survey in surveys:
        ordered[survey.code] = []

    for comment in comments:
        if comment.is_general:
            ordered[GENERAL_GROUP_KEY].append(comment)
        else:
            survey_key = comment.survey_code or "Unknown"
            ordered.setdefault(survey_key, []).append(comment)

    return OrderedDict((k, v) for k, v in ordered.items() if v)


def _sort_comments_for_ruref_display(comments: list[Comment]) -> list[Comment]:
    survey_order_map = _survey_order_map()
    return sorted(
        comments,
        key=lambda comment: (
            0 if comment.is_general else 1,
            survey_order_map.get(comment.survey_code or "", 999),
            -int(comment.period),
            -comment.created_at.timestamp(),
        ),
    )


def _contact_key_for_comment(comment: Comment) -> Optional[str]:
    if comment.is_general:
        return None
    return comment.survey_code


def _contact_has_display_name(contact: Optional[Contact]) -> bool:
    if contact is None:
        return False

    return bool(contact.name.strip())


def _comment_has_contact_snapshot(comment: Comment) -> bool:
    return bool((comment.contact_name_snapshot or "").strip())


def _comment_contact_for_display(
    comment: Comment,
    contacts_for_scope: dict[Optional[str], Contact],
) -> Optional[dict[str, str]]:
    if _comment_has_contact_snapshot(comment):
        return {
            "name": comment.contact_name_snapshot,
            "telephone_number": comment.contact_phone_snapshot,
            "email_address": comment.contact_email_snapshot,
            "id": "",
        }

    contact = contacts_for_scope.get(_contact_key_for_comment(comment))
    if contact is None or not _contact_has_display_name(contact):
        return None

    return {
        "name": contact.name,
        "telephone_number": contact.telephone_number,
        "email_address": contact.email_address,
        "id": str(contact.id),
    }


def _contacts_for_ruref(ruref: str) -> dict[Optional[str], Contact]:
    contacts = Contact.query.filter_by(ruref=ruref).all()
    return {contact.survey_code: contact for contact in contacts}


def _contacts_for_rurefs(rurefs: set[str]) -> dict[str, dict[Optional[str], Contact]]:
    if not rurefs:
        return {}

    contacts = Contact.query.filter(Contact.ruref.in_(sorted(rurefs))).all()
    contacts_by_ruref: dict[str, dict[Optional[str], Contact]] = {}
    for contact in contacts:
        contacts_by_ruref.setdefault(contact.ruref, {})[contact.survey_code] = contact

    return contacts_by_ruref


def _sort_contacts_for_display(contacts: list[Contact]) -> list[Contact]:
    survey_order_map = _survey_order_map()
    return sorted(
        contacts,
        key=lambda contact: (
            contact.ruref,
            0 if contact.survey_code is None else 1,
            survey_order_map.get(contact.survey_code or "", 999),
            contact.survey_code or "",
            contact.id,
        ),
    )


def _contact_has_matching_comment(contact: Contact) -> bool:
    if contact.survey_code is None:
        return (
            Comment.query.filter_by(ruref=contact.ruref, is_general=True).first()
            is not None
        )

    return (
        Comment.query.filter_by(
            ruref=contact.ruref, survey_code=contact.survey_code
        ).first()
        is not None
    )


def _cleanup_orphan_contacts() -> int:
    orphan_ids: list[int] = []
    for contact in Contact.query.all():
        if not _contact_has_matching_comment(contact):
            orphan_ids.append(contact.id)

    if not orphan_ids:
        return 0

    Contact.query.filter(Contact.id.in_(orphan_ids)).delete(synchronize_session=False)
    db.session.commit()
    return len(orphan_ids)


def _load_lowest_ruref_comment_groups(
    limit: int = 10,
) -> OrderedDict[str, OrderedDict[str, list[Comment]]]:
    rurefs = [
        row[0]
        for row in db.session.query(distinct(Comment.ruref))
        .order_by(Comment.ruref.asc())
        .limit(limit)
        .all()
    ]

    grouped_by_ruref: OrderedDict[str, OrderedDict[str, list[Comment]]] = OrderedDict()
    if not rurefs:
        return grouped_by_ruref

    comments = Comment.query.filter(Comment.ruref.in_(rurefs)).all()
    comments_by_ruref: dict[str, list[Comment]] = {ruref: [] for ruref in rurefs}
    for comment in comments:
        comments_by_ruref.setdefault(comment.ruref, []).append(comment)

    for ruref in rurefs:
        grouped_by_ruref[ruref] = _group_comments(
            _sort_comments_for_ruref_display(comments_by_ruref[ruref])
        )

    return grouped_by_ruref


@bp.get("/comments")
@login_required
def index():
    ruref = request.args.get("ruref", "").strip()
    query_text = request.args.get("q", "").strip()
    selected_surveys = request.args.getlist("surveys")
    show_comments = _query_flag("show_comments", default=False)
    show_contacts = _query_flag("show_contacts", default=False)
    add_tab_active = request.args.get("tab") == "add"
    add_ruref = request.args.get("add_ruref", "").strip()
    add_survey = request.args.get("add_survey", "").strip()
    add_period = request.args.get("add_period", "").strip()
    add_comment = request.args.get("add_comment", "").strip()
    add_is_general = request.args.get("add_is_general") == "1"
    add_contact_name = request.args.get("add_contact_name", "").strip()
    add_contact_phone = request.args.get("add_contact_phone", "").strip()
    add_contact_email = request.args.get("add_contact_email", "").strip()
    search_performed = show_comments or bool(ruref or query_text or selected_surveys)

    surveys = (
        Survey.query.filter_by(is_active=True)
        .order_by(Survey.display_order.asc())
        .all()
    )
    comments = []
    grouped_results = OrderedDict()
    ruref_groups = OrderedDict()
    contacts_by_ruref: dict[str, dict[Optional[str], Contact]] = {}
    reporting_units_with_comments = (
        db.session.query(db.func.count(distinct(Comment.ruref))).scalar() or 0
    )
    total_comments = db.session.query(db.func.count(Comment.id)).scalar() or 0

    if show_comments:
        ruref_groups = _load_lowest_ruref_comment_groups()
    elif search_performed:
        comment_query = Comment.query

        if ruref:
            if is_valid_ruref(ruref):
                comment_query = comment_query.filter(Comment.ruref == ruref)
            else:
                flash("RUREF must be exactly 11 numeric characters.", "error")
                comment_query = comment_query.filter(False)

        if selected_surveys:
            comment_query = comment_query.filter(
                or_(
                    Comment.survey_code.in_(selected_surveys),
                    Comment.is_general.is_(True),
                )
            )

        if query_text:
            like_pattern = f"%{query_text}%"
            comment_query = comment_query.filter(
                or_(
                    Comment.comment_text.ilike(like_pattern),
                    Comment.ruref.ilike(like_pattern),
                    Comment.period.ilike(like_pattern),
                    Comment.survey_code.ilike(like_pattern),
                    Comment.author.has(User.full_name.ilike(like_pattern)),
                    Comment.author.has(User.username.ilike(like_pattern)),
                )
            )

        comments = (
            comment_query.order_by(Comment.period.desc(), Comment.created_at.desc())
            .limit(300)
            .all()
        )
        grouped_results = _group_comments(comments)

    if show_contacts and search_performed:
        result_rurefs: set[str] = set()
        for comment in comments:
            result_rurefs.add(comment.ruref)
        for result_ruref, grouped_comments in ruref_groups.items():
            if grouped_comments:
                result_rurefs.add(result_ruref)

        contacts_by_ruref = _contacts_for_rurefs(result_rurefs)

    return render_template(
        "comments/index.html",
        comments=comments,
        grouped_results=grouped_results,
        ruref_groups=ruref_groups,
        contacts_by_ruref=contacts_by_ruref,
        show_contacts=show_contacts,
        comment_contact_for_display=_comment_contact_for_display,
        search_performed=search_performed,
        show_comments=show_comments,
        reporting_units_with_comments=_format_count_for_display(
            reporting_units_with_comments
        ),
        total_comments=_format_count_for_display(total_comments),
        surveys=surveys,
        selected_surveys=selected_surveys,
        ruref=ruref,
        q=query_text,
        add_tab_active=add_tab_active,
        add_ruref=add_ruref,
        add_survey=add_survey,
        add_period=add_period,
        add_comment=add_comment,
        add_is_general=add_is_general,
        add_contact_name=add_contact_name,
        add_contact_phone=add_contact_phone,
        add_contact_email=add_contact_email,
    )


@bp.get("/help")
@login_required
def help_page():
    return render_template("help/index.html")


@bp.get("/comments/by-author")
@login_required
def comments_by_author():
    author_filter = request.args.get("author", "").strip()
    page = request.args.get("page", default=1, type=int)
    per_page = 50

    author_query = db.session.query(User.id, User.full_name, User.username).join(
        Comment, Comment.author_id == User.id
    )

    if author_filter:
        like_pattern = f"%{author_filter}%"
        author_query = author_query.filter(
            or_(
                User.full_name.ilike(like_pattern),
                User.username.ilike(like_pattern),
            )
        )

    author_query = author_query.group_by(
        User.id, User.full_name, User.username
    ).order_by(
        User.full_name.asc(),
        User.username.asc(),
    )

    pagination = author_query.paginate(page=page, per_page=per_page, error_out=False)
    page_authors = pagination.items
    page_author_ids = [author_id for author_id, _, _ in page_authors]

    comments: list[Comment] = []
    if page_author_ids:
        comments = (
            Comment.query.join(User, Comment.author_id == User.id)
            .outerjoin(Survey, Comment.survey_code == Survey.code)
            .filter(Comment.author_id.in_(page_author_ids))
            .order_by(
                User.full_name.asc(),
                User.username.asc(),
                Comment.ruref.asc(),
                Comment.is_general.desc(),
                Survey.display_order.asc(),
                Comment.survey_code.asc(),
                Comment.period.desc(),
                Comment.created_at.desc(),
            )
            .all()
        )

    comments_by_author: OrderedDict[tuple[int, str, str], list[Comment]] = OrderedDict()
    for comment in comments:
        author_key = (
            comment.author.id,
            comment.author.full_name,
            comment.author.username,
        )
        comments_by_author.setdefault(author_key, []).append(comment)

    counts_by_author = {}
    if page_author_ids:
        count_query = (
            db.session.query(User.id, db.func.count(Comment.id))
            .join(Comment, Comment.author_id == User.id)
            .filter(User.id.in_(page_author_ids))
            .group_by(User.id)
        )
        counts_by_author = {author_id: count for author_id, count in count_query.all()}

    return render_template(
        "comments/by_author.html",
        author_filter=author_filter,
        comments_by_author=comments_by_author,
        counts_by_author=counts_by_author,
        pagination=pagination,
    )


@bp.get("/comments/by-date")
@login_required
def comments_by_date():
    selected_year = request.args.get("year", type=int)
    selected_month = request.args.get("month", type=int)
    page = request.args.get("page", default=1, type=int)
    per_page = 50

    created_dates = db.session.query(Comment.created_at).all()
    grouped_by_date: OrderedDict[int, OrderedDict[int, int]] = OrderedDict()
    year_counts: dict[int, int] = {}
    month_counts: dict[tuple[int, int], int] = {}

    for (created_at,) in created_dates:
        year = created_at.year
        month = created_at.month

        year_group = grouped_by_date.setdefault(year, OrderedDict())
        year_group[month] = year_group.get(month, 0) + 1

        year_counts[year] = year_counts.get(year, 0) + 1
        month_key = (year, month)
        month_counts[month_key] = month_counts.get(month_key, 0) + 1

    sorted_grouped_by_date: OrderedDict[int, OrderedDict[int, int]] = OrderedDict()
    for year in sorted(grouped_by_date.keys(), reverse=True):
        sorted_grouped_by_date[year] = OrderedDict(
            (month, grouped_by_date[year][month])
            for month in sorted(grouped_by_date[year].keys(), reverse=True)
        )

    selected_month_valid = (
        selected_year is not None
        and selected_month is not None
        and 1 <= selected_month <= 12
        and selected_year in sorted_grouped_by_date
        and selected_month in sorted_grouped_by_date[selected_year]
    )

    selected_month_groups: OrderedDict[str, OrderedDict[str, list[Comment]]] = (
        OrderedDict()
    )
    pagination = None
    if selected_month_valid:
        survey_order_map = _survey_order_map()
        month_query = (
            Comment.query.outerjoin(Survey, Comment.survey_code == Survey.code)
            .filter(
                db.extract("year", Comment.created_at) == selected_year,
                db.extract("month", Comment.created_at) == selected_month,
            )
            .order_by(
                Comment.ruref.asc(),
                Comment.is_general.desc(),
                Survey.display_order.asc(),
                Comment.survey_code.asc(),
                Comment.created_at.desc(),
                Comment.id.desc(),
            )
        )
        pagination = month_query.paginate(page=page, per_page=per_page, error_out=False)

        month_comments = sorted(
            pagination.items,
            key=lambda comment: (
                comment.ruref,
                0 if comment.is_general else 1,
                survey_order_map.get(comment.survey_code or "", 999),
                comment.survey_code or "",
                -comment.created_at.timestamp(),
                -comment.id,
            ),
        )

        for comment in month_comments:
            ruref_group = selected_month_groups.setdefault(comment.ruref, OrderedDict())
            survey_label = (
                GENERAL_GROUP_KEY
                if comment.is_general
                else (comment.survey_code or "Unknown")
            )
            ruref_group.setdefault(survey_label, []).append(comment)

    month_names = {month: calendar.month_name[month] for month in range(1, 13)}

    return render_template(
        "comments/by_date.html",
        grouped_by_date=sorted_grouped_by_date,
        year_counts=year_counts,
        month_counts=month_counts,
        month_names=month_names,
        selected_year=selected_year if selected_month_valid else None,
        selected_month=selected_month if selected_month_valid else None,
        selected_month_groups=selected_month_groups,
        pagination=pagination,
    )


@bp.get("/contacts-management")
@login_required
def contact_management():
    deleted_orphans = _cleanup_orphan_contacts()
    if deleted_orphans:
        flash(
            f"Removed {deleted_orphans} orphan contacts with no matching comments.",
            "info",
        )

    ruref = request.args.get("ruref", "").strip()
    show_all_contacts = _query_flag("show_all_contacts", default=False)
    search_performed = show_all_contacts or bool(ruref)

    contacts: list[Contact] = []
    if show_all_contacts:
        contacts = Contact.query.all()
    elif ruref:
        if is_valid_ruref(ruref):
            contacts = Contact.query.filter_by(ruref=ruref).all()
        else:
            flash("RUREF must be exactly 11 numeric characters.", "error")

    grouped_contacts: OrderedDict[str, list[Contact]] = OrderedDict()
    for contact in _sort_contacts_for_display(contacts):
        grouped_contacts.setdefault(contact.ruref, []).append(contact)

    return render_template(
        "comments/contact_management.html",
        ruref=ruref,
        show_all_contacts=show_all_contacts,
        search_performed=search_performed,
        grouped_contacts=grouped_contacts,
    )


@bp.post("/comments/new")
@login_required
def create_comment():
    ruref = request.form.get("ruref", "").strip()
    survey_code = request.form.get("survey", "").strip()
    period = request.form.get("period", "").strip()
    comment_text = request.form.get("comment", "").strip()
    is_general = request.form.get("is_general") == "1"
    contact_name = request.form.get("contact_name", "").strip()
    contact_phone = request.form.get("contact_phone", "").strip()
    contact_email = request.form.get("contact_email", "").strip()

    valid = True

    if not is_valid_ruref(ruref):
        flash(
            "Reporting Unit Reference must be exactly 11 numeric characters.", "error"
        )
        valid = False

    if not is_valid_period(period):
        flash("Period must be in YYYYMM format and represent a valid month.", "error")
        valid = False

    survey = None
    contact_survey_code: Optional[str] = None

    if not is_general:
        survey = db.session.get(Survey, survey_code)
        if survey is None or not survey.is_active:
            flash("Survey must be selected from the configured survey list.", "error")
            valid = False
        elif not is_period_allowed_for_survey(survey.code, survey.periodicity, period):
            flash("Period month must match the selected survey periodicity.", "error")
            valid = False
        contact_survey_code = survey_code

    if not comment_text:
        flash("Comment cannot be empty.", "error")
        valid = False

    has_contact_input = bool(contact_name or contact_phone or contact_email)
    existing_contact_for_scope = Contact.query.filter_by(
        ruref=ruref, survey_code=contact_survey_code
    ).first()
    create_new_contact = has_contact_input
    contact_to_update: Optional[Contact] = None
    if has_contact_input:
        existing_contact = existing_contact_for_scope
        if existing_contact is not None:
            existing_name = (existing_contact.name or "").strip()
            existing_phone = (existing_contact.telephone_number or "").strip()
            existing_email = (existing_contact.email_address or "").strip()
            input_matches_existing = (
                contact_name == existing_name
                and contact_phone == existing_phone
                and contact_email == existing_email
            )

            if input_matches_existing:
                create_new_contact = False
            else:
                create_new_contact = False
                contact_to_update = existing_contact

    if not valid:
        return redirect(url_for("comments.index", ruref=ruref))

    reporting_unit = db.session.get(ReportingUnit, ruref)
    if reporting_unit is None:
        reporting_unit = ReportingUnit(ruref=ruref)
        db.session.add(reporting_unit)

    comment = Comment(
        ruref=ruref,
        survey_code=survey_code if not is_general else None,
        is_general=is_general,
        period=period,
        comment_text=comment_text,
        contact_name_snapshot=(
            contact_name
            if has_contact_input
            else (existing_contact_for_scope.name if existing_contact_for_scope else "")
        ),
        contact_phone_snapshot=(
            contact_phone
            if has_contact_input
            else (
                existing_contact_for_scope.telephone_number
                if existing_contact_for_scope
                else ""
            )
        ),
        contact_email_snapshot=(
            contact_email
            if has_contact_input
            else (
                existing_contact_for_scope.email_address
                if existing_contact_for_scope
                else ""
            )
        ),
        author_id=current_user.id,
    )
    db.session.add(comment)

    contact_was_amended = contact_to_update is not None

    if create_new_contact:
        db.session.add(
            Contact(
                ruref=ruref,
                survey_code=contact_survey_code,
                name=contact_name,
                telephone_number=contact_phone,
                email_address=contact_email,
            )
        )
    elif contact_to_update is not None:
        contact_to_update.name = contact_name
        contact_to_update.telephone_number = contact_phone
        contact_to_update.email_address = contact_email

    db.session.commit()

    if contact_was_amended:
        flash("Comment saved. Contact details amended.", "success")
    else:
        flash("Comment saved.", "success")
    return redirect(url_for("comments.ruref_detail", ruref=ruref))


@bp.post("/comments/check-contact")
@login_required
def check_contact():
    ruref = request.form.get("ruref", "").strip()
    survey_code = request.form.get("survey", "").strip()
    is_general = request.form.get("is_general") == "1"
    redirect_params = _add_comment_form_state(request.form)

    if not is_valid_ruref(ruref):
        flash(
            "Reporting Unit Reference must be exactly 11 numeric characters.", "error"
        )
        return redirect(url_for("comments.index", **redirect_params))

    contact_survey_code: Optional[str] = None
    if not is_general:
        survey = db.session.get(Survey, survey_code)
        if survey is None or not survey.is_active:
            flash("Survey must be selected from the configured survey list.", "error")
            return redirect(url_for("comments.index", **redirect_params))
        contact_survey_code = survey_code

    existing_contact = Contact.query.filter_by(
        ruref=ruref, survey_code=contact_survey_code
    ).first()
    if existing_contact is not None:
        scope = (
            "general comment"
            if contact_survey_code is None
            else f"survey {contact_survey_code}"
        )
        redirect_params["add_contact_name"] = existing_contact.name or ""
        redirect_params["add_contact_phone"] = (
            existing_contact.telephone_number or ""
        )
        redirect_params["add_contact_email"] = existing_contact.email_address or ""
        flash(
            f"An existing contact was found for this reporting unit and {scope}. Contact fields have been pre-filled.",
            "info",
        )
        return redirect(url_for("comments.index", **redirect_params))

    scope = (
        "general comment"
        if contact_survey_code is None
        else f"survey {contact_survey_code}"
    )
    flash(f"No existing contact was found for this reporting unit and {scope}.", "info")
    return redirect(url_for("comments.index", **redirect_params))


@bp.get("/comments/contact-prefill")
@login_required
def contact_prefill():
    ruref = request.args.get("ruref", "").strip()
    survey_code = request.args.get("survey", "").strip()
    is_general = request.args.get("is_general") == "1"

    if not is_valid_ruref(ruref):
        return jsonify({"found": False})

    contact_survey_code: Optional[str] = None
    if not is_general:
        survey = db.session.get(Survey, survey_code)
        if survey is None or not survey.is_active:
            return jsonify({"found": False})
        contact_survey_code = survey_code

    existing_contact = Contact.query.filter_by(
        ruref=ruref, survey_code=contact_survey_code
    ).first()
    if existing_contact is None:
        return jsonify({"found": False})

    return jsonify(
        {
            "found": True,
            "name": existing_contact.name or "",
            "telephone_number": existing_contact.telephone_number or "",
            "email_address": existing_contact.email_address or "",
        }
    )


@bp.get("/ruref/<ruref>")
@login_required
def ruref_detail(ruref: str):
    if not is_valid_ruref(ruref):
        flash("RUREF must be exactly 11 numeric characters.", "error")
        return redirect(url_for("comments.index"))

    selected_surveys = request.args.getlist("surveys")
    query_text = request.args.get("q", "").strip()
    show_contacts = _query_flag("show_contacts", default=False)

    comment_query = Comment.query.filter(Comment.ruref == ruref)

    if selected_surveys:
        comment_query = comment_query.filter(
            or_(Comment.survey_code.in_(selected_surveys), Comment.is_general.is_(True))
        )

    if query_text:
        comment_query = comment_query.filter(
            Comment.comment_text.ilike(f"%{query_text}%")
        )

    comments = comment_query.all()
    comments = _sort_comments_for_ruref_display(comments)

    grouped_comments = _group_comments(comments)
    contacts_by_survey = _contacts_for_ruref(ruref)
    surveys = (
        Survey.query.filter_by(is_active=True)
        .order_by(Survey.display_order.asc())
        .all()
    )

    return render_template(
        "comments/ruref_detail.html",
        ruref=ruref,
        grouped_comments=grouped_comments,
        contacts_by_survey=contacts_by_survey,
        show_contacts=show_contacts,
        comment_contact_for_display=_comment_contact_for_display,
        surveys=surveys,
        selected_surveys=selected_surveys,
        q=query_text,
    )


@bp.route("/comments/<int:comment_id>/edit", methods=["GET", "POST"])
@login_required
def edit_comment(comment_id: int):
    comment = db.session.get(Comment, comment_id)
    if comment is None:
        flash("Comment not found.", "error")
        return redirect(url_for("comments.index"))

    if request.method == "POST":
        new_text = request.form.get("comment", "").strip()
        if not new_text:
            flash("Comment text cannot be empty.", "error")
            return render_template("comments/edit_comment.html", comment=comment)

        if new_text != comment.comment_text:
            edit = CommentEdit(
                comment_id=comment.id,
                editor_id=current_user.id,
                previous_text=comment.comment_text,
                new_text=new_text,
            )
            comment.comment_text = new_text
            db.session.add(edit)
            db.session.commit()
            flash("Comment updated.", "success")
        else:
            flash("No changes were made.", "info")

        return redirect(url_for("comments.ruref_detail", ruref=comment.ruref))

    return render_template("comments/edit_comment.html", comment=comment)


@bp.route("/contacts/<int:contact_id>/edit", methods=["GET", "POST"])
@login_required
def edit_contact(contact_id: int):
    contact = db.session.get(Contact, contact_id)
    return_state = _add_comment_return_state(request.values)
    has_return_state = _has_add_comment_return_state(return_state)

    if contact is None:
        flash("Contact not found.", "error")
        return redirect(url_for("comments.index"))

    if not _contact_has_matching_comment(contact):
        db.session.delete(contact)
        db.session.commit()
        flash("Contact has no matching comment and was removed.", "error")
        return redirect(url_for("comments.contact_management"))

    if request.method == "POST":
        contact.name = request.form.get("name", "").strip()
        contact.telephone_number = request.form.get("telephone_number", "").strip()
        contact.email_address = request.form.get("email_address", "").strip()
        db.session.commit()
        flash("Contact updated.", "success")

        if has_return_state:
            return redirect(url_for("comments.index", **return_state))

        return redirect(url_for("comments.ruref_detail", ruref=contact.ruref))

    return render_template(
        "comments/edit_contact.html",
        contact=contact,
        return_state=return_state,
        has_return_state=has_return_state,
    )

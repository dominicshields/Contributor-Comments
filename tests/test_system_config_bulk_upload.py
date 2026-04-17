from __future__ import annotations

import io
from datetime import UTC, datetime

from app.extensions import db
from app.models import Comment, CommentEdit, ReportingUnit, Survey, User


def test_system_config_menu_includes_bulk_upload_for_admin(client, login_admin):
    response = client.get("/comments", follow_redirects=True)
    assert response.status_code == 200
    assert b"System Config" in response.data
    assert b"System Info" in response.data
    assert b"Help" in response.data
    assert b"Bulk Upload Comments" in response.data
    assert b"Delete All Comments" in response.data
    assert b"Survey Metadata" in response.data


def test_survey_metadata_nav_visible_to_non_admin_but_not_system_config(client, login_analyst):
    response = client.get("/comments", follow_redirects=True)
    assert response.status_code == 200
    assert b"Survey Metadata" in response.data
    assert b"Help" in response.data
    assert b"System Config" not in response.data


def test_bulk_upload_page_requires_admin(client, login_analyst):
    response = client.get("/admin/system-config/bulk-upload-comments", follow_redirects=True)
    assert response.status_code == 200
    assert b"Admin access required" in response.data


def test_delete_all_comments_page_requires_admin(client, login_analyst):
    response = client.get("/admin/system-config/delete-all-comments", follow_redirects=True)
    assert response.status_code == 200
    assert b"Admin access required" in response.data


def test_system_info_page_requires_admin(client, login_analyst):
    response = client.get("/admin/system-config/system-info", follow_redirects=True)
    assert response.status_code == 200
    assert b"Admin access required" in response.data


def test_bulk_upload_comments_imports_valid_rows_and_skips_invalid(client, login_admin, app):
    with app.app_context():
        survey_221 = db.session.get(Survey, "221")
        assert survey_221 is not None
        survey_221.periodicity = "Annual"
        db.session.commit()

    csv_text = "\n".join(
        [
            "ruref,survey_code,period,comment_text,author_name,saved_at",
            "12345678901,221,202312,Valid annual period row,Analyst Bulk,2024-01-15 10:00:00",
            "12345678902,221,202311,Invalid annual period row,Analyst Bulk,2024-01-15 10:00:00",
            "12345678903,999,202312,Unknown survey row,Analyst Bulk,2024-01-15 10:00:00",
        ]
    )

    response = client.post(
        "/admin/system-config/bulk-upload-comments",
        data={"comments_file": (io.BytesIO(csv_text.encode("utf-8")), "upload.csv")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Bulk upload complete. Added 1 comments in " in response.data
    assert b" seconds. Skipped: 2." in response.data

    with app.app_context():
        comments = Comment.query.filter_by(survey_code="221").all()
        assert len(comments) == 1
        assert comments[0].ruref == "12345678901"
        assert comments[0].period == "202312"


def test_delete_all_comments_removes_comments_and_edit_history(client, login_admin, app):
    with app.app_context():
        survey = db.session.get(Survey, "221")
        assert survey is not None

        author = User.query.filter_by(username="analyst1").first()
        editor = User.query.filter_by(username="admin").first()
        assert author is not None
        assert editor is not None

        ruref = "12345678901"
        reporting_unit = db.session.get(ReportingUnit, ruref)
        if reporting_unit is None:
            reporting_unit = ReportingUnit(ruref=ruref)
            db.session.add(reporting_unit)

        comment = Comment(
            ruref=ruref,
            survey_code="221",
            period="202312",
            comment_text="Before delete",
            author_id=author.id,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        db.session.add(comment)
        db.session.flush()

        db.session.add(
            CommentEdit(
                comment_id=comment.id,
                editor_id=editor.id,
                previous_text="Before",
                new_text="After",
                edited_at=datetime.now(UTC),
            )
        )
        db.session.commit()

        assert Comment.query.count() >= 1
        assert CommentEdit.query.count() >= 1

    response = client.post("/admin/system-config/delete-all-comments", follow_redirects=True)
    assert response.status_code == 200
    assert b"All comments deleted." in response.data

    with app.app_context():
        assert Comment.query.count() == 0
        assert CommentEdit.query.count() == 0


def test_system_info_page_displays_comment_counts(client, login_admin, app):
    with app.app_context():
        author_one = User.query.filter_by(username="analyst1").first()
        author_two = User.query.filter_by(username="analyst2").first()
        assert author_one is not None
        assert author_two is not None

        for ruref in ("12345678901", "12345678902"):
            reporting_unit = db.session.get(ReportingUnit, ruref)
            if reporting_unit is None:
                db.session.add(ReportingUnit(ruref=ruref))

        db.session.add_all(
            [
                Comment(
                    ruref="12345678901",
                    survey_code="221",
                    period="202401",
                    comment_text="First",
                    author_id=author_one.id,
                    created_at=datetime.now(UTC),
                    updated_at=datetime.now(UTC),
                ),
                Comment(
                    ruref="12345678901",
                    survey_code="221",
                    period="202401",
                    comment_text="Second",
                    author_id=author_two.id,
                    created_at=datetime.now(UTC),
                    updated_at=datetime.now(UTC),
                ),
                Comment(
                    ruref="12345678902",
                    survey_code="241",
                    period="202312",
                    comment_text="Third",
                    author_id=author_two.id,
                    created_at=datetime.now(UTC),
                    updated_at=datetime.now(UTC),
                ),
            ]
        )
        db.session.commit()

    response = client.get("/admin/system-config/system-info", follow_redirects=True)

    assert response.status_code == 200
    assert b"Number of Reporting Units With comments" in response.data
    assert b"2" in response.data
    assert b"Total number of comments" in response.data
    assert b"3" in response.data
    assert b"Total number of comment authors" in response.data
    assert b"Database size" in response.data
    assert b"In-memory database" in response.data
    assert b"Count of comments by each survey code" in response.data
    assert b"221" in response.data
    assert b"241" in response.data
    assert b"202401" in response.data
    assert b"202312" in response.data

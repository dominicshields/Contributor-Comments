from __future__ import annotations

import io
from datetime import UTC, datetime

from app.extensions import db
from app.models import Comment, CommentEdit, Contact, ReportingUnit, Survey, User


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


def test_bulk_upload_comments_imports_general_rows_with_is_general_flag(client, login_admin, app):
    csv_text = "\n".join(
        [
            "ruref,period,comment_text,is_general,survey_code,author_name,saved_at",
            "12345678911,202312,General comment with flag,1,,Analyst Bulk,2024-01-15 10:00:00",
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

    with app.app_context():
        comments = Comment.query.filter_by(ruref="12345678911").all()
        assert len(comments) == 1
        assert comments[0].is_general is True
        assert comments[0].survey_code is None


def test_bulk_upload_comments_treats_blank_survey_as_general_comment(client, login_admin, app):
    csv_text = "\n".join(
        [
            "ruref,period,comment_text,survey_code,author_name,saved_at",
            "12345678912,202401,General comment via blank survey,,Analyst Bulk,2024-02-10 10:00:00",
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

    with app.app_context():
        comments = Comment.query.filter_by(ruref="12345678912").all()
        assert len(comments) == 1
        assert comments[0].is_general is True
        assert comments[0].survey_code is None


def test_bulk_upload_comments_creates_contact_from_contact_columns(client, login_admin, app):
    csv_text = "\n".join(
        [
            "ruref,survey_code,period,comment_text,contact_name,contact_phone,contact_email",
            "12345678913,221,202312,Comment with contact,Pat Contact,07123456789,pat@example.com",
        ]
    )

    response = client.post(
        "/admin/system-config/bulk-upload-comments",
        data={"comments_file": (io.BytesIO(csv_text.encode("utf-8")), "upload.csv")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )

    assert response.status_code == 200

    with app.app_context():
        contact = Contact.query.filter_by(ruref="12345678913", survey_code="221").first()
        assert contact is not None
        assert contact.name == "Pat Contact"
        assert contact.telephone_number == "07123456789"
        assert contact.email_address == "pat@example.com"


def test_bulk_upload_comments_upserts_contact_without_duplicate_scope(client, login_admin, app):
    csv_text = "\n".join(
        [
            "ruref,survey_code,period,comment_text,contact_name,contact_phone,contact_email",
            "12345678914,221,202312,First row,Initial Name,07000000000,initial@example.com",
            "12345678914,221,202401,Second row,Updated Name,07999999999,updated@example.com",
        ]
    )

    response = client.post(
        "/admin/system-config/bulk-upload-comments",
        data={"comments_file": (io.BytesIO(csv_text.encode("utf-8")), "upload.csv")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )

    assert response.status_code == 200

    with app.app_context():
        contacts = Contact.query.filter_by(ruref="12345678914", survey_code="221").all()
        assert len(contacts) == 1
        assert contacts[0].name == "Updated Name"
        assert contacts[0].telephone_number == "07999999999"
        assert contacts[0].email_address == "updated@example.com"


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
        db.session.add(
            Contact(
                ruref=ruref,
                survey_code="221",
                name="Pat Contact",
                telephone_number="07123456789",
                email_address="pat@example.com",
            )
        )
        db.session.commit()

        assert Comment.query.count() >= 1
        assert CommentEdit.query.count() >= 1
        assert Contact.query.count() >= 1

    response = client.post("/admin/system-config/delete-all-comments", follow_redirects=True)
    assert response.status_code == 200
    assert b"All comments deleted." in response.data

    with app.app_context():
        assert Comment.query.count() == 0
        assert CommentEdit.query.count() == 0
        assert Contact.query.count() == 0


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
        db.session.add_all(
            [
                Contact(
                    ruref="12345678901",
                    survey_code="221",
                    name="Survey Contact",
                    telephone_number="07000000001",
                    email_address="survey@example.com",
                ),
                Contact(
                    ruref="12345678902",
                    survey_code=None,
                    name="General Contact",
                    telephone_number="07000000002",
                    email_address="general@example.com",
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
    assert b"Contacts" in response.data
    assert b"Contacts Summary" in response.data
    assert b"Number of Reporting Units With contacts" in response.data
    assert b"Total number of contacts" in response.data
    assert b"Count of contacts by survey code" in response.data
    assert b"General" in response.data

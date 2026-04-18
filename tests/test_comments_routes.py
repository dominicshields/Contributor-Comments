from app.extensions import db
from app.models import Comment, Contact, Survey


def test_create_comment_rejects_invalid_period(client, login_analyst):
    response = client.post(
        "/comments/new",
        data={
            "ruref": "12345678901",
            "survey": "221",
            "period": "202613",
            "comment": "invalid period attempt",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Period must be in YYYYMM format" in response.data


def test_create_comment_rejects_period_not_matching_survey_periodicity(client, login_admin, app):
    with app.app_context():
        survey = db.session.get(Survey, "221")
        assert survey is not None
        survey.periodicity = "Annual"
        db.session.commit()

    response = client.post(
        "/comments/new",
        data={
            "ruref": "12345678901",
            "survey": "221",
            "period": "202611",
            "comment": "invalid month for annual survey",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Period month must match the selected survey periodicity." in response.data


def test_create_comment_accepts_period_matching_survey_periodicity(client, login_admin, app):
    with app.app_context():
        survey = db.session.get(Survey, "221")
        assert survey is not None
        survey.periodicity = "Quarterly"
        db.session.commit()

    response = client.post(
        "/comments/new",
        data={
            "ruref": "12345678901",
            "survey": "221",
            "period": "202612",
            "comment": "valid quarter month",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Comment saved." in response.data


def test_create_and_search_comment_by_ruref(client, login_analyst, app):
    client.post(
        "/comments/new",
        data={
            "ruref": "12345678901",
            "survey": "221",
            "period": "202601",
            "comment": "ONS contributor note",
        },
        follow_redirects=True,
    )

    response = client.get("/comments?ruref=12345678901", follow_redirects=True)
    assert response.status_code == 200
    assert b"ONS contributor note" in response.data


def test_deactivated_survey_not_usable_for_new_comments(client, login_admin, app):
    client.post("/admin/surveys/221/toggle-active", follow_redirects=True)

    response = client.post(
        "/comments/new",
        data={
            "ruref": "12345678901",
            "survey": "221",
            "period": "202602",
            "comment": "should fail",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Survey must be selected from the configured survey list" in response.data

    with app.app_context():
        assert Comment.query.count() == 0
        survey = db.session.get(Survey, "221")
        assert survey is not None
        assert survey.is_active is False


def test_show_comments_returns_lowest_ten_rurefs_grouped_for_display(client, login_analyst):
    test_rows = [
        ("00000000005", "221", "202601", "ruref 5 older"),
        ("00000000005", "221", "202602", "ruref 5 newer"),
        ("00000000005", "241", "202603", "ruref 5 second survey"),
        ("00000000002", "241", "202601", "ruref 2"),
        ("00000000011", "221", "202601", "ruref 11 should be excluded"),
    ]

    for ruref_number in range(1, 12):
        client.post(
            "/comments/new",
            data={
                "ruref": f"{ruref_number:011d}",
                "survey": "221",
                "period": "202601",
                "comment": f"seed comment {ruref_number}",
            },
            follow_redirects=True,
        )

    for ruref, survey, period, text in test_rows:
        client.post(
            "/comments/new",
            data={
                "ruref": ruref,
                "survey": survey,
                "period": period,
                "comment": text,
            },
            follow_redirects=True,
        )

    response = client.get("/comments?show_comments=1", follow_redirects=True)

    assert response.status_code == 200
    assert b"RUREF 00000000001" in response.data
    assert b"RUREF 00000000010" in response.data
    assert b"RUREF 00000000011" not in response.data
    assert response.data.index(b"RUREF 00000000002") < response.data.index(b"RUREF 00000000005")
    assert response.data.index(b"Survey 221") < response.data.index(b"Survey 241")
    assert response.data.index(b"ruref 5 newer") < response.data.index(b"ruref 5 older")


def test_show_comments_testing_obeys_contact_visibility_toggle(client, login_analyst):
    client.post(
        "/comments/new",
        data={
            "ruref": "12345678901",
            "survey": "221",
            "period": "202601",
            "comment": "testing comments toggle",
            "contact_name": "Pat Contact",
            "contact_phone": "0123456789",
            "contact_email": "pat@example.com",
        },
        follow_redirects=True,
    )

    response_hidden = client.get("/comments?show_comments=1&show_contacts=0", follow_redirects=True)
    assert response_hidden.status_code == 200
    assert b"pat@example.com" not in response_hidden.data

    response_visible = client.get("/comments?show_comments=1&show_contacts=1", follow_redirects=True)
    assert response_visible.status_code == 200
    assert b"pat@example.com" in response_visible.data


def test_search_tab_displays_reporting_unit_and_comment_totals(client, login_analyst):
    client.post(
        "/comments/new",
        data={
            "ruref": "12345678901",
            "survey": "221",
            "period": "202601",
            "comment": "first",
        },
        follow_redirects=True,
    )
    client.post(
        "/comments/new",
        data={
            "ruref": "12345678901",
            "survey": "241",
            "period": "202602",
            "comment": "second",
        },
        follow_redirects=True,
    )
    client.post(
        "/comments/new",
        data={
            "ruref": "12345678902",
            "survey": "221",
            "period": "202603",
            "comment": "third",
        },
        follow_redirects=True,
    )

    response = client.get("/comments", follow_redirects=True)

    assert response.status_code == 200
    assert b"Number of Reporting Units with comments: 2" in response.data
    assert b"Total comments: 3" in response.data


def test_comment_search_highlights_search_term_in_results(client, login_analyst):
    client.post(
        "/comments/new",
        data={
            "ruref": "12345678901",
            "survey": "221",
            "period": "202601",
            "comment": "This is a contributor note.",
        },
        follow_redirects=True,
    )

    response = client.get("/comments?q=contributor", follow_redirects=True)

    assert response.status_code == 200
    assert b"<mark>contributor</mark>" in response.data


def test_comment_search_can_match_author(client, login_analyst):
    client.post(
        "/comments/new",
        data={
            "ruref": "12345678901",
            "survey": "221",
            "period": "202601",
            "comment": "Author searchable comment.",
        },
        follow_redirects=True,
    )

    response = client.get("/comments?q=analyst1", follow_redirects=True)

    assert response.status_code == 200
    assert b"Author searchable comment." in response.data


def test_search_results_show_contact_info_only_when_toggled_on(client, login_analyst):
    client.post(
        "/comments/new",
        data={
            "ruref": "12345678901",
            "survey": "221",
            "period": "202601",
            "comment": "Comment with contact visibility toggle.",
            "contact_name": "Pat Contact",
            "contact_phone": "0123456789",
            "contact_email": "pat@example.com",
        },
        follow_redirects=True,
    )

    response_hidden = client.get("/comments?ruref=12345678901&show_contacts=0", follow_redirects=True)
    assert response_hidden.status_code == 200
    assert b"pat@example.com" not in response_hidden.data

    response_visible = client.get("/comments?ruref=12345678901&show_contacts=1", follow_redirects=True)
    assert response_visible.status_code == 200
    assert b"pat@example.com" in response_visible.data


def test_search_results_duplicate_show_contacts_uses_last_value(client, login_analyst):
    client.post(
        "/comments/new",
        data={
            "ruref": "12345678909",
            "survey": "221",
            "period": "202601",
            "comment": "Duplicate show_contacts query param behavior.",
            "contact_name": "Pat Contact",
            "contact_phone": "0123456789",
            "contact_email": "pat@example.com",
        },
        follow_redirects=True,
    )

    response_last_zero = client.get(
        "/comments?ruref=12345678909&show_contacts=1&show_contacts=0",
        follow_redirects=True,
    )
    assert response_last_zero.status_code == 200
    assert b"pat@example.com" not in response_last_zero.data

    response_last_one = client.get(
        "/comments?ruref=12345678909&show_contacts=0&show_contacts=1",
        follow_redirects=True,
    )
    assert response_last_one.status_code == 200
    assert b"pat@example.com" in response_last_one.data


def test_search_results_show_name_only_contact_when_toggle_on(client, login_analyst, app):
    client.post(
        "/comments/new",
        data={
            "ruref": "12345678905",
            "survey": "221",
            "period": "202601",
            "comment": "Comment with partial contact",
            "contact_name": "Only Name",
        },
        follow_redirects=True,
    )

    response = client.get("/comments?ruref=12345678905&show_contacts=1", follow_redirects=True)
    assert response.status_code == 200
    assert b"Name: Only Name" in response.data
    assert b"Telephone: Not provided" in response.data
    assert b"Email: Not provided" in response.data


def test_help_page_requires_login(client):
    response = client.get("/help", follow_redirects=True)

    assert response.status_code == 200
    assert b"Contributor Comments Sign In" in response.data


def test_help_page_visible_for_logged_in_user(client, login_analyst):
    response = client.get("/help", follow_redirects=True)

    assert response.status_code == 200
    assert b"How to use Contributor Comments day to day." in response.data
    assert b"System Config (Admin)" in response.data


def test_general_comment_is_saved_and_grouped_before_surveys(client, login_analyst):
    client.post(
        "/comments/new",
        data={
            "ruref": "12345678901",
            "is_general": "1",
            "period": "202601",
            "comment": "General context comment",
        },
        follow_redirects=True,
    )

    client.post(
        "/comments/new",
        data={
            "ruref": "12345678901",
            "survey": "221",
            "period": "202601",
            "comment": "Survey-specific comment",
        },
        follow_redirects=True,
    )

    response = client.get("/comments?ruref=12345678901", follow_redirects=True)

    assert response.status_code == 200
    assert b"General" in response.data
    assert response.data.index(b"General") < response.data.index(b"Survey 221")


def test_create_comment_with_contact_creates_contact_record(client, login_analyst, app):
    response = client.post(
        "/comments/new",
        data={
            "ruref": "12345678901",
            "survey": "221",
            "period": "202601",
            "comment": "Comment with contact",
            "contact_name": "Pat Contact",
            "contact_phone": "0123456789",
            "contact_email": "pat@example.com",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200

    with app.app_context():
        contact = Contact.query.filter_by(ruref="12345678901", survey_code="221").first()
        assert contact is not None
        assert contact.name == "Pat Contact"
        assert contact.telephone_number == "0123456789"
        assert contact.email_address == "pat@example.com"


def test_create_comment_rejects_duplicate_contact_for_same_scope(client, login_analyst, app):
    client.post(
        "/comments/new",
        data={
            "ruref": "12345678901",
            "survey": "221",
            "period": "202601",
            "comment": "First",
            "contact_name": "Pat Contact",
            "contact_phone": "0123456789",
            "contact_email": "pat@example.com",
        },
        follow_redirects=True,
    )

    response = client.post(
        "/comments/new",
        data={
            "ruref": "12345678901",
            "survey": "221",
            "period": "202602",
            "comment": "Second",
            "contact_name": "Another Contact",
            "contact_phone": "0123456790",
            "contact_email": "another@example.com",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"A contact already exists for this reporting unit and survey 221." in response.data
    assert b"Edit Contact" in response.data

    with app.app_context():
        contacts = Contact.query.filter_by(ruref="12345678901", survey_code="221").all()
        assert len(contacts) == 1


def test_edit_contact_updates_values(client, login_analyst, app):
    client.post(
        "/comments/new",
        data={
            "ruref": "12345678901",
            "survey": "221",
            "period": "202601",
            "comment": "Comment with contact",
            "contact_name": "Original",
            "contact_phone": "0000",
            "contact_email": "orig@example.com",
        },
        follow_redirects=True,
    )

    with app.app_context():
        contact = Contact.query.filter_by(ruref="12345678901", survey_code="221").first()
        assert contact is not None
        contact_id = contact.id

    response = client.post(
        f"/contacts/{contact_id}/edit",
        data={
            "name": "Updated Name",
            "telephone_number": "1111",
            "email_address": "updated@example.com",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Contact updated." in response.data

    with app.app_context():
        updated = db.session.get(Contact, contact_id)
        assert updated is not None
        assert updated.name == "Updated Name"
        assert updated.telephone_number == "1111"
        assert updated.email_address == "updated@example.com"


def test_ruref_detail_obeys_contact_toggle(client, login_analyst):
    client.post(
        "/comments/new",
        data={
            "ruref": "12345678907",
            "survey": "221",
            "period": "202601",
            "comment": "RUREF detail contact toggle",
            "contact_name": "Pat Contact",
            "contact_phone": "0123456789",
            "contact_email": "pat@example.com",
        },
        follow_redirects=True,
    )

    response_off = client.get("/ruref/12345678907?show_contacts=0", follow_redirects=True)
    assert response_off.status_code == 200
    assert b"pat@example.com" not in response_off.data

    response_on = client.get("/ruref/12345678907?show_contacts=1", follow_redirects=True)
    assert response_on.status_code == 200
    assert b"pat@example.com" in response_on.data

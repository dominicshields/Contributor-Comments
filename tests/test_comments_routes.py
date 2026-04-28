from datetime import datetime, timezone

from app.extensions import db
from app.models import Comment, Contact, ReportingUnit, SiteContent, Survey, User


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


def test_create_comment_rejects_period_not_matching_survey_periodicity(
    client, login_admin, app
):
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


def test_create_comment_accepts_period_matching_survey_periodicity(
    client, login_admin, app
):
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


def test_create_comment_accepts_ni_number_for_ashe_and_normalizes(
    client, login_admin, app
):
    response = client.post(
        "/comments/new",
        data={
            "ruref": "ab 123414 c",
            "survey": "141",
            "period": "202604",
            "comment": "ASHE NI comment",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Comment saved." in response.data
    assert b"NI Number AB123414C" in response.data

    with app.app_context():
        comment = Comment.query.filter_by(survey_code="141").first()
        assert comment is not None
        assert comment.ruref == "AB123414C"


def test_create_comment_rejects_ni_number_for_general_comment(client, login_admin, app):
    response = client.post(
        "/comments/new",
        data={
            "ruref": "AB123414C",
            "is_general": "1",
            "period": "202604",
            "comment": "Should fail",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"NI Numbers can only be used for survey 141 comments." in response.data

    with app.app_context():
        assert Comment.query.filter_by(ruref="AB123414C").count() == 0


def test_invalid_ashe_reference_returns_to_add_tab_with_values_preserved(
    client, login_admin
):
    response = client.post(
        "/comments/new",
        data={
            "ruref": "AB123456C",
            "survey": "141",
            "period": "202604",
            "comment": "Invalid NI draft",
            "contact_name": "Draft Contact",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert (
        b'class="ons-section-nav__link is-active" href="/comments?tab=add'
        in response.data
    )
    assert b"NI Number must be two letters, six digits ending in" in response.data
    assert b'value="AB123456C"' in response.data
    assert b'<option value="141" selected>' in response.data
    assert b"Invalid NI draft" in response.data
    assert b"Draft Contact" in response.data


def test_add_comment_page_contains_ni_number_auto_select_script(client, login_analyst):
    response = client.get("/comments?tab=add", follow_redirects=True)

    assert response.status_code == 200
    assert b"function maybePopulateAsheSurveyFromReference()" in response.data
    assert b"surveySelect.value = '141';" in response.data


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


def test_show_comments_returns_lowest_ten_rurefs_grouped_for_display(
    client, login_analyst
):
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
    assert response.data.index(b"RUREF 00000000002") < response.data.index(
        b"RUREF 00000000005"
    )
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

    response_hidden = client.get(
        "/comments?show_comments=1&show_contacts=0", follow_redirects=True
    )
    assert response_hidden.status_code == 200
    assert b"pat@example.com" not in response_hidden.data

    response_visible = client.get(
        "/comments?show_comments=1&show_contacts=1", follow_redirects=True
    )
    assert response_visible.status_code == 200
    assert b"pat@example.com" in response_visible.data


def test_search_tab_does_not_display_reporting_unit_or_comment_totals(
    client, login_analyst
):
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
    assert b"Number of Reporting Units with comments:" not in response.data
    assert b"Total comments:" not in response.data


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


def test_add_comment_spellcheck_is_disabled_by_default(client, login_analyst):
    response = client.get("/comments?tab=add", follow_redirects=True)

    assert response.status_code == 200
    assert b'id="comment-spellcheck-enabled"' in response.data
    assert b'spellcheck="false"' in response.data


def test_add_comment_spellcheck_preference_persists_per_user(
    client, login_analyst, app
):
    response = client.post(
        "/comments/preferences/spellcheck",
        data={"enabled": "1"},
    )

    assert response.status_code == 200
    assert response.json == {"saved": True, "enabled": True}

    with app.app_context():
        analyst = User.query.filter_by(username="analyst1").first()
        assert analyst is not None
        assert analyst.comment_spellcheck_enabled is True

    updated_page = client.get("/comments?tab=add", follow_redirects=True)
    assert updated_page.status_code == 200
    assert b'id="comment-spellcheck-enabled"' in updated_page.data
    assert b"checked" in updated_page.data
    assert b'spellcheck="true"' in updated_page.data

    disable_response = client.post(
        "/comments/preferences/spellcheck",
        data={"enabled": "0"},
    )

    assert disable_response.status_code == 200
    assert disable_response.json == {"saved": True, "enabled": False}

    with app.app_context():
        analyst = User.query.filter_by(username="analyst1").first()
        assert analyst is not None
        assert analyst.comment_spellcheck_enabled is False


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

    response_hidden = client.get(
        "/comments?ruref=12345678901&show_contacts=0", follow_redirects=True
    )
    assert response_hidden.status_code == 200
    assert b"pat@example.com" not in response_hidden.data

    response_visible = client.get(
        "/comments?ruref=12345678901&show_contacts=1", follow_redirects=True
    )
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


def test_search_results_show_name_only_contact_when_toggle_on(
    client, login_analyst, app
):
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

    response = client.get(
        "/comments?ruref=12345678905&show_contacts=1", follow_redirects=True
    )
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


def test_help_edit_page_requires_admin(client, login_analyst):
    response = client.get("/help/edit", follow_redirects=True)

    assert response.status_code == 200
    assert b"Admin access required." in response.data


def test_help_edit_page_visible_for_admin(client, login_admin):
    response = client.get("/help/edit", follow_redirects=True)

    assert response.status_code == 200
    assert b"Edit Help Page" in response.data


def test_admin_can_update_help_page_content(client, login_admin, app):
    response = client.post(
        "/help/edit",
        data={"content": "Updated help text for admins."},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Help page updated." in response.data
    assert b"Updated help text for admins." in response.data

    with app.app_context():
        stored = db.session.get(SiteContent, "help_page")
        assert stored is not None
        assert stored.content == "Updated help text for admins."


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
        contact = Contact.query.filter_by(
            ruref="12345678901", survey_code="221"
        ).first()
        assert contact is not None
        assert contact.name == "Pat Contact"
        assert contact.telephone_number == "0123456789"
        assert contact.email_address == "pat@example.com"


def test_create_comment_updates_existing_contact_for_same_scope(
    client, login_analyst, app
):
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
    assert b"Comment saved." in response.data

    with app.app_context():
        contacts = Contact.query.filter_by(ruref="12345678901", survey_code="221").all()
        comments = Comment.query.filter_by(ruref="12345678901", survey_code="221").all()
        assert len(comments) == 2
        assert len(contacts) == 1
        assert contacts[0].name == "Another Contact"
        assert contacts[0].telephone_number == "0123456790"
        assert contacts[0].email_address == "another@example.com"

    detail_response = client.get(
        "/ruref/12345678901?show_contacts=1", follow_redirects=True
    )
    assert detail_response.status_code == 200
    assert b"Name: Pat Contact" in detail_response.data
    assert b"Name: Another Contact" in detail_response.data


def test_check_contact_prefills_existing_contact_in_add_form(client, login_analyst):
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
        "/comments/check-contact",
        data={
            "ruref": "12345678901",
            "survey": "221",
            "period": "202602",
            "comment": "Draft follow-up",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert (
        b"An existing contact was found for this reporting unit and survey 221."
        in response.data
    )
    assert b"Edit Contact" not in response.data
    assert (
        b'<textarea class="form-control" id="new-comment" name="comment"'
        in response.data
    )
    assert b"Draft follow-up" in response.data
    assert b'name="contact_name" value="Pat Contact"' in response.data
    assert b'name="contact_phone" value="0123456789"' in response.data
    assert b'name="contact_email" value="pat@example.com"' in response.data


def test_contact_prefill_endpoint_returns_existing_contact(client, login_analyst):
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

    response = client.get(
        "/comments/contact-prefill?ruref=12345678901&survey=221&is_general=0",
        follow_redirects=True,
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload is not None
    assert payload["found"] is True
    assert payload["name"] == "Pat Contact"
    assert payload["telephone_number"] == "0123456789"
    assert payload["email_address"] == "pat@example.com"


def test_create_comment_allows_matching_existing_contact_values(
    client, login_analyst, app
):
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
            "contact_name": "Pat Contact",
            "contact_phone": "0123456789",
            "contact_email": "pat@example.com",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Comment saved." in response.data

    with app.app_context():
        comments = Comment.query.filter_by(ruref="12345678901", survey_code="221").all()
        contacts = Contact.query.filter_by(ruref="12345678901", survey_code="221").all()
        assert len(comments) == 2
        assert len(contacts) == 1


def test_check_contact_returns_to_add_form_when_scope_has_no_contact(
    client, login_analyst
):
    response = client.post(
        "/comments/check-contact",
        data={
            "ruref": "12345678901",
            "survey": "221",
            "period": "202602",
            "comment": "Draft follow-up",
            "contact_name": "Draft Contact",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert (
        b"No existing contact was found for this reporting unit and survey 221."
        in response.data
    )
    assert (
        b'class="ons-section-nav__link is-active" href="/comments?tab=add'
        in response.data
    )
    assert b'value="12345678901"' in response.data
    assert b"Draft follow-up" in response.data
    assert b"Draft Contact" in response.data


def test_edit_contact_returns_to_preserved_add_comment_draft(
    client, login_analyst, app
):
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

    with app.app_context():
        contact = Contact.query.filter_by(
            ruref="12345678901", survey_code="221"
        ).first()
        assert contact is not None
        contact_id = contact.id

    response = client.post(
        f"/contacts/{contact_id}/edit",
        data={
            "name": "Updated Contact",
            "telephone_number": "0999999999",
            "email_address": "updated@example.com",
            "add_ruref": "12345678901",
            "add_survey": "221",
            "add_period": "202602",
            "add_comment": "Draft follow-up",
            "add_is_general": "0",
            "add_contact_name": "",
            "add_contact_phone": "",
            "add_contact_email": "",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Contact updated." in response.data
    assert (
        b'class="ons-section-nav__link is-active" href="/comments?tab=add'
        in response.data
    )
    assert b'value="12345678901"' in response.data
    assert b"Draft follow-up" in response.data

    with app.app_context():
        updated_contact = db.session.get(Contact, contact_id)
        assert updated_contact is not None
        assert updated_contact.name == "Updated Contact"


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
        contact = Contact.query.filter_by(
            ruref="12345678901", survey_code="221"
        ).first()
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

    response_off = client.get(
        "/ruref/12345678907?show_contacts=0", follow_redirects=True
    )
    assert response_off.status_code == 200
    assert b"pat@example.com" not in response_off.data

    response_on = client.get(
        "/ruref/12345678907?show_contacts=1", follow_redirects=True
    )
    assert response_on.status_code == 200
    assert b"pat@example.com" in response_on.data


def test_contact_management_requires_login(client):
    response = client.get("/contacts-management", follow_redirects=True)

    assert response.status_code == 200
    assert b"Contributor Comments Sign In" in response.data


def test_contact_management_search_and_show_all(client, login_analyst, app):
    with app.app_context():
        ru1 = db.session.get(ReportingUnit, "12345678901")
        if ru1 is None:
            ru1 = ReportingUnit(ruref="12345678901")
            db.session.add(ru1)

        ru2 = db.session.get(ReportingUnit, "12345678902")
        if ru2 is None:
            ru2 = ReportingUnit(ruref="12345678902")
            db.session.add(ru2)

        author = User.query.filter_by(username="analyst1").first()
        assert author is not None

        db.session.add_all(
            [
                Comment(
                    ruref="12345678901",
                    survey_code=None,
                    is_general=True,
                    period="202601",
                    comment_text="General comment for RU1",
                    author_id=author.id,
                ),
                Comment(
                    ruref="12345678901",
                    survey_code="241",
                    period="202601",
                    comment_text="Survey 241 comment for RU1",
                    author_id=author.id,
                ),
                Comment(
                    ruref="12345678901",
                    survey_code="221",
                    period="202601",
                    comment_text="Survey 221 comment for RU1",
                    author_id=author.id,
                ),
                Comment(
                    ruref="12345678902",
                    survey_code="221",
                    period="202601",
                    comment_text="Survey 221 comment for RU2",
                    author_id=author.id,
                ),
            ]
        )

        contact_general = Contact(
            ruref="12345678901",
            survey_code=None,
            name="General Contact",
            telephone_number="02070000001",
            email_address="general1@example.com",
        )
        contact_241 = Contact(
            ruref="12345678901",
            survey_code="241",
            name="Survey 241 Contact",
            telephone_number="02070000002",
            email_address="s241@example.com",
        )
        contact_221 = Contact(
            ruref="12345678901",
            survey_code="221",
            name="Survey 221 Contact",
            telephone_number="02070000003",
            email_address="s221@example.com",
        )
        contact_ru2 = Contact(
            ruref="12345678902",
            survey_code="221",
            name="Second RU Contact",
            telephone_number="02070000004",
            email_address="ru2@example.com",
        )
        db.session.add_all([contact_general, contact_241, contact_221, contact_ru2])
        db.session.commit()
        contact_221_id = contact_221.id

    search_response = client.get(
        "/contacts-management?ruref=12345678901", follow_redirects=True
    )
    assert search_response.status_code == 200
    assert b"RUREF 12345678901" in search_response.data
    assert b"RUREF 12345678902" not in search_response.data

    # General first, then survey display order (221 before 241).
    assert search_response.data.index(b"General") < search_response.data.index(
        b"Survey 221"
    )
    assert search_response.data.index(b"Survey 221") < search_response.data.index(
        b"Survey 241"
    )
    assert f"/contacts/{contact_221_id}/edit".encode() in search_response.data

    show_all_response = client.get(
        "/contacts-management?show_all_contacts=1", follow_redirects=True
    )
    assert show_all_response.status_code == 200
    assert b"RUREF 12345678901" in show_all_response.data
    assert b"RUREF 12345678902" in show_all_response.data


def test_contact_management_search_by_name_or_email(client, login_analyst, app):
    with app.app_context():
        ru1 = db.session.get(ReportingUnit, "12345678911")
        if ru1 is None:
            ru1 = ReportingUnit(ruref="12345678911")
            db.session.add(ru1)

        ru2 = db.session.get(ReportingUnit, "12345678912")
        if ru2 is None:
            ru2 = ReportingUnit(ruref="12345678912")
            db.session.add(ru2)

        author = User.query.filter_by(username="analyst1").first()
        assert author is not None

        db.session.add_all(
            [
                Comment(
                    ruref="12345678911",
                    survey_code="221",
                    period="202601",
                    comment_text="Survey 221 comment for RU1",
                    author_id=author.id,
                ),
                Comment(
                    ruref="12345678912",
                    survey_code="221",
                    period="202601",
                    comment_text="Survey 221 comment for RU2",
                    author_id=author.id,
                ),
            ]
        )

        db.session.add_all(
            [
                Contact(
                    ruref="12345678911",
                    survey_code="221",
                    name="Alice Example",
                    telephone_number="02070000011",
                    email_address="alice@example.com",
                ),
                Contact(
                    ruref="12345678912",
                    survey_code="221",
                    name="Bob Example",
                    telephone_number="02070000012",
                    email_address="bob@example.com",
                ),
            ]
        )
        db.session.commit()

    search_by_name_response = client.get(
        "/contacts-management?contact_query=alice",
        follow_redirects=True,
    )
    assert search_by_name_response.status_code == 200
    assert b"Alice Example" in search_by_name_response.data
    assert b"Bob Example" not in search_by_name_response.data

    search_by_email_response = client.get(
        "/contacts-management?contact_query=bob%40example.com",
        follow_redirects=True,
    )
    assert search_by_email_response.status_code == 200
    assert b"Bob Example" in search_by_email_response.data
    assert b"Alice Example" not in search_by_email_response.data


def test_contact_management_removes_orphan_contacts(client, login_analyst, app):
    with app.app_context():
        ru = db.session.get(ReportingUnit, "12345678903")
        if ru is None:
            ru = ReportingUnit(ruref="12345678903")
            db.session.add(ru)

        orphan_contact = Contact(
            ruref="12345678903",
            survey_code="221",
            name="Orphan Contact",
            telephone_number="02070000009",
            email_address="orphan@example.com",
        )
        db.session.add(orphan_contact)
        db.session.commit()

    response = client.get(
        "/contacts-management?show_all_contacts=1", follow_redirects=True
    )
    assert response.status_code == 200
    assert b"Removed 1 orphan contacts with no matching comments." in response.data
    assert b"Orphan Contact" not in response.data

    with app.app_context():
        still_exists = Contact.query.filter_by(
            ruref="12345678903", survey_code="221"
        ).first()
        assert still_exists is None


def test_comments_by_author_requires_login(client):
    response = client.get("/comments/by-author", follow_redirects=True)

    assert response.status_code == 200
    assert b"Contributor Comments Sign In" in response.data


def test_comments_by_author_filter_and_ordering(client, login_admin, app):
    with app.app_context():
        analyst1 = User.query.filter_by(username="analyst1").first()
        analyst2 = User.query.filter_by(username="analyst2").first()
        assert analyst1 is not None
        assert analyst2 is not None

        for ruref in ("12345678001", "12345678002", "12345678003"):
            if db.session.get(ReportingUnit, ruref) is None:
                db.session.add(ReportingUnit(ruref=ruref))

        db.session.add_all(
            [
                Comment(
                    ruref="12345678003",
                    survey_code="241",
                    is_general=False,
                    period="202603",
                    comment_text="alpha second",
                    author_id=analyst1.id,
                ),
                Comment(
                    ruref="12345678001",
                    survey_code=None,
                    is_general=True,
                    period="202603",
                    comment_text="alpha general",
                    author_id=analyst1.id,
                ),
                Comment(
                    ruref="12345678002",
                    survey_code="221",
                    is_general=False,
                    period="202603",
                    comment_text="bravo",
                    author_id=analyst2.id,
                ),
            ]
        )
        db.session.commit()

    response_all = client.get("/comments/by-author", follow_redirects=True)
    assert response_all.status_code == 200
    assert b"analyst1" in response_all.data
    assert b"analyst2" in response_all.data
    assert response_all.data.index(b"analyst1") < response_all.data.index(b"analyst2")
    assert response_all.data.index(b"12345678001") < response_all.data.index(
        b"12345678003"
    )

    response_filtered = client.get(
        "/comments/by-author?author=analyst1", follow_redirects=True
    )
    assert response_filtered.status_code == 200
    assert b"analyst1" in response_filtered.data
    assert b"analyst2" not in response_filtered.data


def test_comments_by_author_pagination_second_page(client, login_admin, app):
    with app.app_context():
        created_usernames = []

        for i in range(55):
            username = f"paging_user_{i:02d}"
            user = User(
                username=username, full_name=f"Paging User {i:02d}", is_admin=False
            )
            user.set_password("Password123!")
            db.session.add(user)
            db.session.flush()

            created_usernames.append(username.encode())

            ruref = f"{20000000000 + i:011d}"
            if db.session.get(ReportingUnit, ruref) is None:
                db.session.add(ReportingUnit(ruref=ruref))

            db.session.add(
                Comment(
                    ruref=ruref,
                    survey_code="221",
                    is_general=False,
                    period="202603",
                    comment_text=f"paginated author comment {i}",
                    author_id=user.id,
                )
            )

        db.session.commit()

    page_one = client.get("/comments/by-author?page=1", follow_redirects=True)
    assert page_one.status_code == 200
    assert created_usernames[0] in page_one.data
    assert created_usernames[49] in page_one.data
    assert created_usernames[50] not in page_one.data

    page_two = client.get("/comments/by-author?page=2", follow_redirects=True)
    assert page_two.status_code == 200
    assert created_usernames[50] in page_two.data
    assert created_usernames[54] in page_two.data
    assert created_usernames[0] not in page_two.data


def test_comments_by_author_paginates_authors_not_comments(client, login_admin, app):
    with app.app_context():
        analyst1 = User.query.filter_by(username="analyst1").first()
        analyst2 = User.query.filter_by(username="analyst2").first()
        assert analyst1 is not None
        assert analyst2 is not None

        for i in range(55):
            ruref = f"{30000000000 + i:011d}"
            if db.session.get(ReportingUnit, ruref) is None:
                db.session.add(ReportingUnit(ruref=ruref))

            db.session.add(
                Comment(
                    ruref=ruref,
                    survey_code="221",
                    is_general=False,
                    period="202603",
                    comment_text=f"heavy author comment {i}",
                    author_id=analyst1.id,
                )
            )

        second_author_ruref = "39999999999"
        if db.session.get(ReportingUnit, second_author_ruref) is None:
            db.session.add(ReportingUnit(ruref=second_author_ruref))

        db.session.add(
            Comment(
                ruref=second_author_ruref,
                survey_code="221",
                is_general=False,
                period="202603",
                comment_text="second author marker",
                author_id=analyst2.id,
            )
        )
        db.session.commit()

    response = client.get("/comments/by-author?page=1", follow_redirects=True)

    assert response.status_code == 200
    assert b"analyst1" in response.data
    assert b"analyst2" in response.data
    assert b"second author marker" in response.data


def test_comments_by_author_invalid_page_defaults_to_first_page(
    client, login_admin, app
):
    with app.app_context():
        analyst1 = User.query.filter_by(username="analyst1").first()
        assert analyst1 is not None

        ruref = "29999999999"
        if db.session.get(ReportingUnit, ruref) is None:
            db.session.add(ReportingUnit(ruref=ruref))

        db.session.add(
            Comment(
                ruref=ruref,
                survey_code="221",
                is_general=False,
                period="202603",
                comment_text="invalid page fallback marker",
                author_id=analyst1.id,
            )
        )
        db.session.commit()

    response = client.get(
        "/comments/by-author?page=not-a-number", follow_redirects=True
    )

    assert response.status_code == 200
    assert b"invalid page fallback marker" in response.data


def test_comments_by_date_requires_login(client):
    response = client.get("/comments/by-date", follow_redirects=True)

    assert response.status_code == 200
    assert b"Contributor Comments Sign In" in response.data


def test_comments_by_date_grouping_order_and_counts(client, login_admin, app):
    with app.app_context():
        analyst1 = User.query.filter_by(username="analyst1").first()
        assert analyst1 is not None

        for ruref in ("12345678101", "12345678102"):
            if db.session.get(ReportingUnit, ruref) is None:
                db.session.add(ReportingUnit(ruref=ruref))

        db.session.add_all(
            [
                Comment(
                    ruref="12345678102",
                    survey_code="241",
                    is_general=False,
                    period="202604",
                    comment_text="april ruref two survey",
                    author_id=analyst1.id,
                    created_at=datetime(2026, 4, 10, 9, 0, tzinfo=timezone.utc),
                ),
                Comment(
                    ruref="12345678101",
                    survey_code=None,
                    is_general=True,
                    period="202604",
                    comment_text="april general",
                    author_id=analyst1.id,
                    created_at=datetime(2026, 4, 9, 9, 0, tzinfo=timezone.utc),
                ),
                Comment(
                    ruref="12345678101",
                    survey_code="221",
                    is_general=False,
                    period="202604",
                    comment_text="april survey",
                    author_id=analyst1.id,
                    created_at=datetime(2026, 4, 8, 9, 0, tzinfo=timezone.utc),
                ),
                Comment(
                    ruref="12345678101",
                    survey_code="221",
                    is_general=False,
                    period="202603",
                    comment_text="march survey",
                    author_id=analyst1.id,
                    created_at=datetime(2026, 3, 5, 9, 0, tzinfo=timezone.utc),
                ),
            ]
        )
        db.session.commit()

    response = client.get("/comments/by-date", follow_redirects=True)

    assert response.status_code == 200
    assert b"Collapse all" in response.data
    assert b"Expand all" in response.data
    assert b"2026 (4)" in response.data
    assert b"April (3)" in response.data
    assert b"March (1)" in response.data
    assert response.data.index(b"April (3)") < response.data.index(b"March (1)")
    assert b"april general" not in response.data
    assert b"march survey" not in response.data


def test_comments_by_date_open_month_shows_grouped_comments(client, login_admin, app):
    with app.app_context():
        analyst1 = User.query.filter_by(username="analyst1").first()
        assert analyst1 is not None

        for ruref in ("12345678201", "12345678202"):
            if db.session.get(ReportingUnit, ruref) is None:
                db.session.add(ReportingUnit(ruref=ruref))

        db.session.add_all(
            [
                Comment(
                    ruref="12345678201",
                    survey_code=None,
                    is_general=True,
                    period="202604",
                    comment_text="open month general",
                    author_id=analyst1.id,
                    created_at=datetime(2026, 4, 10, 9, 0, tzinfo=timezone.utc),
                ),
                Comment(
                    ruref="12345678201",
                    survey_code="221",
                    is_general=False,
                    period="202604",
                    comment_text="open month survey",
                    author_id=analyst1.id,
                    created_at=datetime(2026, 4, 9, 9, 0, tzinfo=timezone.utc),
                ),
                Comment(
                    ruref="12345678202",
                    survey_code="241",
                    is_general=False,
                    period="202604",
                    comment_text="open month ruref two",
                    author_id=analyst1.id,
                    created_at=datetime(2026, 4, 8, 9, 0, tzinfo=timezone.utc),
                ),
            ]
        )
        db.session.commit()

    response = client.get("/comments/by-date?year=2026&month=4", follow_redirects=True)

    assert response.status_code == 200
    assert b"April 2026" in response.data
    assert response.data.index(b"RUREF 12345678201") < response.data.index(
        b"RUREF 12345678202"
    )
    assert response.data.index(b"General") < response.data.index(b"221")
    assert b"open month general" in response.data
    assert b"open month survey" in response.data
    assert b"open month ruref two" in response.data
    assert b'id="selected-month-results"' in response.data
    assert (
        b"/comments/by-date?year=2026&amp;month=4&amp;page=1#selected-month-results"
        in response.data
    )


def test_comments_by_date_invalid_page_defaults_to_first_page(client, login_admin, app):
    with app.app_context():
        analyst1 = User.query.filter_by(username="analyst1").first()
        assert analyst1 is not None

        ruref = "18888888888"
        if db.session.get(ReportingUnit, ruref) is None:
            db.session.add(ReportingUnit(ruref=ruref))

        db.session.add(
            Comment(
                ruref=ruref,
                survey_code="221",
                is_general=False,
                period="202604",
                comment_text="by date invalid page marker",
                author_id=analyst1.id,
            )
        )
        db.session.commit()

    response = client.get(
        "/comments/by-date?year=2026&month=4&page=not-a-number", follow_redirects=True
    )

    assert response.status_code == 200
    assert b"by date invalid page marker" in response.data


def test_comments_by_date_month_pagination_second_page(client, login_admin, app):
    with app.app_context():
        analyst1 = User.query.filter_by(username="analyst1").first()
        assert analyst1 is not None

        for i in range(55):
            ruref = f"{17700000000 + i:011d}"
            if db.session.get(ReportingUnit, ruref) is None:
                db.session.add(ReportingUnit(ruref=ruref))

            db.session.add(
                Comment(
                    ruref=ruref,
                    survey_code="221",
                    is_general=False,
                    period="202604",
                    comment_text=f"month page marker {i}",
                    author_id=analyst1.id,
                    created_at=datetime(2026, 4, 10, 9, 0, tzinfo=timezone.utc),
                )
            )

        db.session.commit()

    page_one = client.get(
        "/comments/by-date?year=2026&month=4&page=1", follow_redirects=True
    )
    assert page_one.status_code == 200
    assert b"month page marker 0" in page_one.data
    assert b"month page marker 49" in page_one.data
    assert b"month page marker 50" not in page_one.data

    page_two = client.get(
        "/comments/by-date?year=2026&month=4&page=2", follow_redirects=True
    )
    assert page_two.status_code == 200
    assert b"month page marker 50" in page_two.data
    assert b"month page marker 54" in page_two.data
    assert b"month page marker 0" not in page_two.data
    assert (
        b"/comments/by-date?year=2026&amp;month=4&amp;page=1#selected-month-results"
        in page_two.data
    )
    assert (
        b"/comments/by-date?year=2026&amp;month=4&amp;page=2#selected-month-results"
        in page_two.data
    )

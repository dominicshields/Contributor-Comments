from app.extensions import db
from app.models import Comment, Survey


def test_admin_surveys_page_displays_codes_in_ascending_order(client, login_admin):
    response = client.get("/admin/surveys", follow_redirects=True)
    assert response.status_code == 200

    page = response.data.decode("utf-8")
    index_002 = page.find("<td>002</td>")
    index_023 = page.find("<td>023</td>")
    index_138 = page.find("<td>138</td>")
    index_221 = page.find("<td>221</td>")
    index_241 = page.find("<td>241</td>")

    assert index_002 < index_023 < index_138 < index_221 < index_241


def test_admin_surveys_page_sorts_by_description_with_code_as_tie_breaker(
    client, login_admin, app
):
    with app.app_context():
        survey_777 = db.session.get(Survey, "777")
        if survey_777 is None:
            survey_777 = Survey(
                code="777",
                display_order=900,
                description="Alpha",
                periodicity="Monthly",
                forms_per_period=1,
                is_active=True,
            )
            db.session.add(survey_777)

        survey_778 = db.session.get(Survey, "778")
        if survey_778 is None:
            survey_778 = Survey(
                code="778",
                display_order=901,
                description="Alpha",
                periodicity="Monthly",
                forms_per_period=1,
                is_active=True,
            )
            db.session.add(survey_778)

        survey_779 = db.session.get(Survey, "779")
        if survey_779 is None:
            survey_779 = Survey(
                code="779",
                display_order=902,
                description="Zulu",
                periodicity="Monthly",
                forms_per_period=1,
                is_active=True,
            )
            db.session.add(survey_779)

        db.session.commit()

    response = client.get("/admin/surveys?sort=description", follow_redirects=True)
    assert response.status_code == 200

    page = response.data.decode("utf-8")
    index_777 = page.find("<td>777</td>")
    index_778 = page.find("<td>778</td>")
    index_779 = page.find("<td>779</td>")

    assert index_777 < index_778 < index_779


def test_non_admin_can_view_survey_metadata_page(client, login_analyst):
    response = client.get("/admin/surveys", follow_redirects=True)
    assert response.status_code == 200
    assert b"Survey Metadata" in response.data
    assert b"Current Surveys" in response.data
    assert b"Add Survey" not in response.data
    assert b"Import Surveys" not in response.data


def test_admin_surveys_page_has_import_button(client, login_admin):
    response = client.get("/admin/surveys", follow_redirects=True)
    assert response.status_code == 200
    assert b"Import Surveys" in response.data


def test_admin_can_toggle_survey_activation(client, login_admin, app):
    response = client.post("/admin/surveys/221/toggle-active", follow_redirects=True)
    assert response.status_code == 200

    with app.app_context():
        survey = db.session.get(Survey, "221")
        assert survey is not None
        assert survey.is_active is False


def test_admin_can_update_survey_metadata(client, login_admin, app):
    response = client.post(
        "/admin/surveys/221/metadata",
        data={
            "description": "Annual Contributors Survey",
            "periodicity": "Quarterly",
            "forms_per_period": "120",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200

    with app.app_context():
        survey = db.session.get(Survey, "221")
        assert survey is not None
        assert survey.description == "Annual Contributors Survey"
        assert survey.periodicity == "Quarterly"
        assert survey.forms_per_period == 120


def test_admin_can_add_survey_with_metadata(client, login_admin, app):
    response = client.post(
        "/admin/surveys",
        data={
            "code": "777",
            "description": "Test New Survey",
            "periodicity": "Monthly",
            "forms_per_period": "42",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200

    with app.app_context():
        survey = db.session.get(Survey, "777")
        assert survey is not None
        assert survey.description == "Test New Survey"
        assert survey.periodicity == "Monthly"
        assert survey.forms_per_period == 42


def test_admin_can_delete_survey_completely(client, login_admin, app):
    create_response = client.post(
        "/comments/new",
        data={
            "ruref": "12345678901",
            "survey": "221",
            "period": "202601",
            "comment": "Comment to be removed with survey",
        },
        follow_redirects=True,
    )
    assert create_response.status_code == 200

    response = client.post("/admin/surveys/221/delete", follow_redirects=True)
    assert response.status_code == 200

    with app.app_context():
        survey = db.session.get(Survey, "221")
        assert survey is None
        comments_for_survey = Comment.query.filter_by(survey_code="221").count()
        assert comments_for_survey == 0


def test_admin_rejects_invalid_periodicity(client, login_admin, app):
    response = client.post(
        "/admin/surveys",
        data={
            "code": "778",
            "description": "Invalid periodicity survey",
            "periodicity": "Weekly",
            "forms_per_period": "12",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Survey periodicity must be one of" in response.data

    with app.app_context():
        survey = db.session.get(Survey, "778")
        assert survey is None


def test_admin_can_import_surveys_from_csv(client, login_admin, app):
    response = client.post("/admin/surveys/import", follow_redirects=True)
    assert response.status_code == 200
    assert b"Surveys import complete." in response.data

    with app.app_context():
        imported = db.session.get(Survey, "001")
        assert imported is not None
        assert imported.description == "OLD - ABI  (97)"
        assert imported.periodicity == "Annual"
        assert imported.forms_per_period == 20700

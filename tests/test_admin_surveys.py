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
        data={"description": "Annual Contributors Survey", "forms_per_period": "120"},
        follow_redirects=True,
    )
    assert response.status_code == 200

    with app.app_context():
        survey = db.session.get(Survey, "221")
        assert survey is not None
        assert survey.description == "Annual Contributors Survey"
        assert survey.forms_per_period == 120


def test_admin_can_add_survey_with_metadata(client, login_admin, app):
    response = client.post(
        "/admin/surveys",
        data={"code": "777", "description": "Test New Survey", "forms_per_period": "42"},
        follow_redirects=True,
    )
    assert response.status_code == 200

    with app.app_context():
        survey = db.session.get(Survey, "777")
        assert survey is not None
        assert survey.description == "Test New Survey"
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

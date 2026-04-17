from app.validation import is_period_allowed_for_survey, is_valid_period, is_valid_ruref


def test_ruref_validation():
    assert is_valid_ruref("12345678901")
    assert not is_valid_ruref("123")
    assert not is_valid_ruref("1234567890A")


def test_period_validation():
    assert is_valid_period("202601")
    assert is_valid_period("199001")
    assert not is_valid_period("202613")
    assert not is_valid_period("20260A")
    assert not is_valid_period("2026")


def test_periodicity_month_rules():
    assert is_period_allowed_for_survey("221", "Monthly", "202601")
    assert is_period_allowed_for_survey("221", "Quarterly", "202603")
    assert not is_period_allowed_for_survey("221", "Quarterly", "202604")
    assert is_period_allowed_for_survey("221", "Annual", "202612")
    assert not is_period_allowed_for_survey("221", "Annual", "202611")
    assert is_period_allowed_for_survey("141", "Monthly", "202604")
    assert not is_period_allowed_for_survey("141", "Monthly", "202605")

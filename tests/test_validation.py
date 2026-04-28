from app.validation import (
    is_period_allowed_for_survey,
    is_valid_ni_number,
    is_valid_period,
    is_valid_reference,
    is_valid_reference_for_survey,
    is_valid_ruref,
    normalize_reference,
)


def test_ruref_validation():
    assert is_valid_ruref("12345678901")
    assert not is_valid_ruref("123")
    assert not is_valid_ruref("1234567890A")


def test_ni_number_validation():
    assert is_valid_ni_number("AB123414C")
    assert is_valid_ni_number("ab 123414 c")
    assert not is_valid_ni_number("A123414C")
    assert not is_valid_ni_number("AB123456C")
    assert not is_valid_ni_number("AB1234141")


def test_generic_reference_validation():
    assert normalize_reference("ab 123414 c") == "AB123414C"
    assert is_valid_reference("12345678901")
    assert is_valid_reference("AB123414C")
    assert not is_valid_reference("AB123456C")


def test_reference_validation_is_survey_aware():
    assert is_valid_reference_for_survey("AB123414C", "141")
    assert not is_valid_reference_for_survey("12345678901", "141")
    assert is_valid_reference_for_survey("12345678901", "221")
    assert not is_valid_reference_for_survey("AB123414C", "221")


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

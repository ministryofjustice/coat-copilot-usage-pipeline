from datetime import date

import pytest
import dates


def test_empty_range_returns_single_day():
    # single_day is used verbatim; today is irrelevant here.
    assert dates.report_days("", "2026-06-15", date(2026, 7, 1)) == ["2026-06-15"]


def test_week_from_monday_to_yesterday():
    # 2026-07-01 is a Wednesday; Monday of that week is 2026-06-29, yesterday 06-30.
    assert dates.report_days("week", "ignored", date(2026, 7, 1)) == [
        "2026-06-29",
        "2026-06-30",
    ]


def test_week_on_monday_falls_back_to_yesterday():
    # 2026-07-06 is a Monday; week start == today > yesterday -> just yesterday.
    assert dates.report_days("week", "ignored", date(2026, 7, 6)) == ["2026-07-05"]


def test_month_from_first_to_yesterday():
    # 2026-07-03: first of month 07-01, yesterday 07-02.
    assert dates.report_days("month", "ignored", date(2026, 7, 3)) == [
        "2026-07-01",
        "2026-07-02",
    ]


def test_month_on_first_falls_back_to_yesterday():
    # 2026-07-01: month start == today > yesterday (06-30) -> just yesterday.
    assert dates.report_days("month", "ignored", date(2026, 7, 1)) == ["2026-06-30"]


def test_invalid_range_raises():
    with pytest.raises(ValueError):
        dates.report_days("quarter", "ignored", date(2026, 7, 1))

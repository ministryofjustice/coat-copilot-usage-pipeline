from datetime import timedelta

VALID_RANGES = ("week", "month")


def report_days(backfill_range, single_day, today):
    """Return the list of ISO day strings (YYYY-MM-DD) to process.

    - backfill_range "" (empty) -> [single_day] (single day; unchanged behaviour).
    - "week"  -> Monday of today's week .. yesterday (UTC), inclusive.
    - "month" -> first of today's month .. yesterday (UTC), inclusive.

    Ranges always end yesterday and ignore single_day. `today` is a
    datetime.date (UTC). When the computed start is after yesterday (today is a
    Monday for "week", or the 1st for "month"), the range collapses to
    [yesterday] so the job never does nothing. Unknown values raise ValueError.
    """
    if not backfill_range:
        return [single_day]
    if backfill_range not in VALID_RANGES:
        raise ValueError(
            f"BACKFILL_RANGE must be empty, 'week' or 'month'; got {backfill_range!r}"
        )

    yesterday = today - timedelta(days=1)
    if backfill_range == "week":
        start = today - timedelta(days=today.weekday())  # Monday of today's week
    else:  # month
        start = today.replace(day=1)  # first of today's month

    if start > yesterday:
        start = yesterday  # today is Monday / the 1st -> just yesterday

    n = (yesterday - start).days + 1
    return [(start + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(n)]

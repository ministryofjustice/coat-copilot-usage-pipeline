from datetime import datetime, timedelta


def report_days(backfill_start_date, single_day, today):
    """Return the list of ISO day strings (YYYY-MM-DD) to process.

    - backfill_start_date "" (empty) -> [single_day] (single day; unchanged behaviour).
    - Otherwise, backfill_start_date must be an ISO date string like "2026-07-20".
      The function returns all dates from that start date through yesterday, inclusive.

    Ranges always end yesterday and ignore single_day. `today` is a
    datetime.date (UTC). If the start date is after yesterday, the range
    collapses to [yesterday] so the job never does nothing. Invalid values
    raise ValueError.
    """
    if not backfill_start_date:
        return [single_day]

    try:
        start = datetime.strptime(backfill_start_date, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError(
            f"BACKFILL_START_DATE must be empty or in YYYY-MM-DD format; got {backfill_start_date!r}"
        ) from exc

    yesterday = today - timedelta(days=1)

    if start > yesterday:
        start = yesterday  # future date / today -> just yesterday

    n = (yesterday - start).days + 1
    return [(start + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(n)]
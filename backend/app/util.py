"""Small helpers shared between routers."""

import datetime as dt


def zero_filled_days(rows, days: int) -> list[dict]:
    """Turn grouped (day, count) rows into a continuous daily series.

    Days without alerts are absent from the GROUP BY result; charts then
    interpolate across the gap (BUG-20). Emit every calendar day of the
    window with an explicit 0 instead. `str(r.day)` normalizes the SQLite
    (string) vs Postgres (date) difference.
    """
    counts = {str(r.day): r.count for r in rows}
    today = dt.datetime.now(dt.UTC).date()
    start = today - dt.timedelta(days=days)
    return [
        {"day": str(start + dt.timedelta(days=i)), "count": counts.get(str(start + dt.timedelta(days=i)), 0)}
        for i in range((today - start).days + 1)
    ]

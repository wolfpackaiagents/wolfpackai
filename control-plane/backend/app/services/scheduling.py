"""Deterministic schedule calculation shared by API and future workers."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("Datetime must include a timezone")
    return value.astimezone(timezone.utc)


def timezone_for(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError as error:
        raise ValueError("Unknown timezone") from error


def validate_cron(expression: str) -> None:
    fields = expression.split()
    if len(fields) != 5:
        raise ValueError("Cron expression must have five fields")
    limits = ((0, 59), (0, 23), (1, 31), (1, 12), (0, 6))
    for field, (minimum, maximum) in zip(fields, limits):
        _cron_values(field, minimum, maximum)


def next_run_at(schedule_type: str, now: datetime, *, at: datetime | None = None, interval_seconds: int | None = None, cron: str | None = None, timezone_name: str = "UTC") -> datetime | None:
    """Return the first strictly future UTC occurrence from immutable schedule inputs."""
    now = as_utc(now)
    if schedule_type == "at":
        if at is None:
            raise ValueError("'at' is required for at schedules")
        candidate = as_utc(at)
        return candidate if candidate > now else None
    if schedule_type == "interval":
        if interval_seconds is None or interval_seconds < 1:
            raise ValueError("interval_seconds must be positive")
        return now + timedelta(seconds=interval_seconds)
    if schedule_type == "cron":
        if not cron:
            raise ValueError("cron is required for cron schedules")
        validate_cron(cron)
        zone = timezone_for(timezone_name)
        minute = now.replace(second=0, microsecond=0) + timedelta(minutes=1)
        minute_field, hour_field, day_field, month_field, weekday_field = cron.split()
        minute_values = _cron_values(minute_field, 0, 59)
        hour_values = _cron_values(hour_field, 0, 23)
        day_values = _cron_values(day_field, 1, 31)
        month_values = _cron_values(month_field, 1, 12)
        weekday_values = _cron_values(weekday_field, 0, 6)
        # Search real UTC minutes so nonexistent and repeated wall-clock minutes follow DST safely.
        for _ in range(5 * 366 * 24 * 60):
            local_minute = minute.astimezone(zone)
            day_matches = local_minute.day in day_values
            weekday_matches = (local_minute.weekday() + 1) % 7 in weekday_values
            calendar_matches = day_matches and weekday_matches if day_field == "*" or weekday_field == "*" else day_matches or weekday_matches
            if (
                local_minute.minute in minute_values
                and local_minute.hour in hour_values
                and calendar_matches
                and local_minute.month in month_values
            ):
                return minute
            minute += timedelta(minutes=1)
        raise ValueError("Cron expression has no occurrence in the next five years")
    raise ValueError("Unknown schedule type")


def occurrence_key(trigger: str, scheduled_for: datetime, idempotency_key: str | None = None) -> str:
    if trigger == "manual":
        if not idempotency_key:
            raise ValueError("idempotency_key is required for manual runs")
        return f"manual:{idempotency_key}"
    return f"scheduled:{as_utc(scheduled_for).isoformat()}"


def _cron_values(field: str, minimum: int, maximum: int) -> set[int]:
    values: set[int] = set()
    for part in field.split(","):
        base, separator, step_text = part.partition("/")
        step = int(step_text) if separator and step_text.isdigit() else 1
        if separator and (not step_text.isdigit() or step < 1):
            raise ValueError("Invalid cron step")
        if base == "*":
            start, end = minimum, maximum
        elif "-" in base:
            start_text, end_text = base.split("-", 1)
            if not start_text.isdigit() or not end_text.isdigit():
                raise ValueError("Invalid cron range")
            start, end = int(start_text), int(end_text)
        elif base.isdigit():
            start = end = int(base)
        else:
            raise ValueError("Invalid cron field")
        if start < minimum or end > maximum or start > end:
            raise ValueError("Cron value outside allowed range")
        values.update(range(start, end + 1, step))
    return values

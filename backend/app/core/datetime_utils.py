from datetime import datetime, timezone


def utc_now() -> datetime:
    """Return the current time as a timezone-AWARE UTC datetime.

    This previously returned a naive datetime, because SQLModel mapped
    `datetime` fields to TIMESTAMP WITHOUT TIME ZONE and asyncpg refuses to
    bind aware values to naive columns.

    SQLModel >= 0.0.44 maps `datetime` to UTCDateTime (TIMESTAMPTZ) instead,
    and that type RAISES on naive input. Storing aware UTC in TIMESTAMPTZ is
    the correct choice anyway: it removes a whole class of "which timezone is
    this?" bug, and because the bind hook rejects naive values, any producer
    that forgets a tzinfo fails loudly at write time instead of silently
    recording the wrong instant.
    """
    return datetime.now(timezone.utc)


def as_utc(value: datetime | None) -> datetime | None:
    """Attach UTC to a naive datetime, or convert an aware one to UTC.

    Parsed dates (strptime on scraped text, ISO strings coerced by pydantic)
    are naive by construction. Run them through this before they reach the
    database.
    """
    if value is None:
        return None
    if value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)

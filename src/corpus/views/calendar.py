"""CalendarDay: public holidays (the `holidays` library, by country code) and the lunar date (`lunardate`) of every day.

Output: data/<city>/views/calendar.json = {city, country, years, days: [{date, lunar: {year, month, day, leap},
holiday: name | None}]}. The holiday names are the library's; nothing here adds or removes a holiday by hand.
"""

from datetime import date, timedelta

from .common import ViewError, config, now, read_json, views_dir, write_json


def path(city: str):
    return views_dir(city) / "calendar.json"


def public_holidays(country: str, years: list[int]) -> dict[date, str]:
    """{date: name} from the `holidays` library, in Vietnamese when the country has that translation."""
    import holidays
    try:
        table = holidays.country_holidays(country, years=years, language="vi")
    except (NotImplementedError, ValueError):   # the country has no Vietnamese names; the library's own are better than none
        table = holidays.country_holidays(country, years=years)
    return dict(table.items())


def lunar_of(d: date) -> dict:
    from lunardate import LunarDate
    ld = LunarDate.from_solar_date(d.year, d.month, d.day)
    return {"year": ld.year, "month": ld.month, "day": ld.day, "leap": bool(ld.is_leap_month)}


def days(first_year: int, last_year: int, holiday_fn=public_holidays, lunar_fn=lunar_of, country: str = "VN") -> list[dict]:
    """One CalendarDay per day of first_year..last_year; the sources are injectable for tests."""
    if last_year < first_year:
        raise ViewError(f"calendar years {first_year}..{last_year}")
    names = holiday_fn(country, list(range(first_year, last_year + 1)))
    out, d = [], date(first_year, 1, 1)
    while d <= date(last_year, 12, 31):
        out.append({"date": d.isoformat(), "lunar": lunar_fn(d), "holiday": names.get(d)})
        d += timedelta(days=1)
    return out


def build(city: str) -> dict:
    """Write data/<city>/views/calendar.json. The calendar is national; it is stored per city so every view of a
    city lives in one folder."""
    cfg = config()["calendar"]
    view = {"city": city, "country": cfg["country"], "years": [cfg["first_year"], cfg["last_year"]], "built_at": now(),
            "source": "holidays+lunardate",
            "days": days(cfg["first_year"], cfg["last_year"], country=cfg["country"])}
    write_json(path(city), view)
    return view


def load(city: str) -> dict | None:
    """The built view, or None when it was never built."""
    return read_json(path(city))

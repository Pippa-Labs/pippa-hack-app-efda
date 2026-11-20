"""CampusFit's sample data and scheduling logic.

Deliberately free of the Pippa SDK, so it can be previewed with plain Python
(`python3 preview.py`) as well as being called from `app.py`.

Everything here is SAMPLE data for a demo: one student's weekly timetable,
a handful of Imperial clubs and some Imperial and Union events. It repeats
every week, so the app always has something upcoming to talk about.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

LONDON = ZoneInfo("Europe/London")

WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")

# ── Campuses and how long it takes to get between them (minutes) ────────────

SAME_CAMPUS_MINUTES = 10  # walking between buildings on one campus

_TRAVEL = {
    frozenset({"South Kensington", "White City"}): 35,
    frozenset({"South Kensington", "Hammersmith"}): 30,
    frozenset({"South Kensington", "St Mary's"}): 25,
    frozenset({"White City", "Hammersmith"}): 20,
    frozenset({"White City", "St Mary's"}): 30,
    frozenset({"Hammersmith", "St Mary's"}): 30,
}


def travel_minutes(origin: str, destination: str) -> int:
    if origin == destination:
        return SAME_CAMPUS_MINUTES
    return _TRAVEL[frozenset({origin, destination})]


# ── Sample data ─────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Slot:
    """Something that happens every week: a class, a session or an event."""

    title: str
    weekday: int          # 0 = Monday
    start: time
    end: time
    campus: str
    venue: str = ""
    host: str = ""        # for events: "Imperial" or "Union"


def _t(text: str) -> time:
    hours, minutes = text.split(":")
    return time(int(hours), int(minutes))


def _slot(title, day, start, end, campus, venue="", host=""):
    return Slot(title, WEEKDAYS.index(day), _t(start), _t(end), campus, venue, host)


#: A sample second-year timetable.
TIMETABLE = (
    _slot("Thermodynamics lecture", "Mon", "10:00", "12:00", "South Kensington"),
    _slot("Maths tutorial", "Mon", "14:00", "16:00", "South Kensington"),
    _slot("Fluid Mechanics lecture", "Tue", "09:00", "11:00", "South Kensington"),
    _slot("Process lab", "Tue", "14:00", "18:00", "White City"),
    _slot("Programming lecture", "Wed", "10:00", "12:00", "South Kensington"),
    _slot("Separation Processes lecture", "Thu", "11:00", "13:00", "South Kensington"),
    _slot("Design project", "Thu", "15:00", "17:00", "South Kensington"),
    _slot("Reaction Engineering lecture", "Fri", "09:00", "11:00", "Hammersmith"),
    _slot("Seminar", "Fri", "13:00", "15:00", "South Kensington"),
)

#: Weekly sessions of some Imperial clubs. Judo has two on purpose: the
#: Tuesday one starts 15 minutes after a lab at White City ends, which is not
#: enough to get back to South Kensington, and the Thursday one fits.
CLUB_SESSIONS = {
    "Judo": (
        _slot("Judo", "Tue", "18:15", "20:00", "South Kensington", "Ethos Sports Centre"),
        _slot("Judo", "Thu", "19:00", "21:00", "South Kensington", "Ethos Sports Centre"),
    ),
    "Climbing": (
        _slot("Climbing", "Mon", "15:30", "17:30", "South Kensington", "Ethos climbing wall"),
        _slot("Climbing", "Wed", "13:00", "15:00", "South Kensington", "Ethos climbing wall"),
    ),
    "Badminton": (
        _slot("Badminton", "Wed", "14:00", "16:00", "South Kensington", "Ethos sports hall"),
        _slot("Badminton", "Fri", "18:00", "20:00", "South Kensington", "Ethos sports hall"),
    ),
    "Chess": (
        _slot("Chess", "Thu", "18:00", "20:00", "South Kensington", "Union Building"),
    ),
    "Dance": (
        _slot("Dance", "Fri", "11:00", "12:30", "White City", "Sir Michael Uren Hub"),
    ),
}

#: Clubs a student "follows" when they do not name any.
DEFAULT_FOLLOWED = ("Judo", "Climbing")

#: Sample Imperial and Union events for Discover.
EVENTS = (
    _slot("Careers fair: engineering and tech", "Wed", "13:00", "16:00",
          "South Kensington", "Great Hall", "Imperial"),
    _slot("Public lecture: climate and energy", "Thu", "18:00", "19:30",
          "South Kensington", "Great Hall", "Imperial"),
    _slot("Innovation showcase", "Tue", "16:00", "18:00",
          "White City", "Translation & Innovation Hub", "Imperial"),
    _slot("Quiz night", "Mon", "19:00", "21:00",
          "South Kensington", "Union bar", "Union"),
    _slot("Society fair", "Wed", "12:30", "14:00",
          "South Kensington", "Union Building", "Union"),
    _slot("Karaoke night", "Fri", "20:00", "23:00",
          "South Kensington", "Union bar", "Union"),
)

HOSTS = ("Imperial", "Union")

# ── Logic ───────────────────────────────────────────────────────────────────

_NOISE = {"club", "clubs", "society", "soc", "icu", "imperial", "the", "session",
          "sessions", "training", "practice", "and", "&"}


class UnknownClub(ValueError):
    def __init__(self, name: str):
        super().__init__(name)
        self.name = name


def parse_clubs(text: str | None) -> list[str]:
    """`"judo, Climbing club and chess"` -> `["Judo", "Climbing", "Chess"]`."""
    cleaned = (text or "").replace(" and ", ",").replace("&", ",").replace(";", ",")
    found: list[str] = []
    for part in cleaned.split(","):
        words = [w for w in part.lower().split() if w not in _NOISE]
        if not words:
            continue
        name = " ".join(words)
        match = next((c for c in CLUB_SESSIONS if c.lower() == name), None)
        if match is None:
            raise UnknownClub(part.strip())
        if match not in found:
            found.append(match)
    return found


@dataclass(frozen=True)
class Occurrence:
    slot: Slot
    start: datetime
    end: datetime
    clash: str | None      # why the student cannot go, or None if it fits

    def describe(self) -> str:
        where = f"{self.slot.venue}, {self.slot.campus}" if self.slot.venue else self.slot.campus
        host = f"{self.slot.host}: " if self.slot.host else ""
        verdict = f"clashes: {self.clash}" if self.clash else "fits"
        return f"{host}{self.slot.title}, {when(self.start, self.end)} at {where} ({verdict})"


def when(start: datetime, end: datetime) -> str:
    # Built by hand: `%-d` is a GNU extension and fails on Windows.
    return (f"{WEEKDAYS[start.weekday()]} {start.day} {MONTHS[start.month - 1]} "
            f"{start:%H:%M}-{end:%H:%M}")


def clash_reason(slot: Slot) -> str | None:
    """Why `slot` does not fit the timetable, allowing travel time, or None."""
    start, end = _minutes(slot.start), _minutes(slot.end)
    for lesson in TIMETABLE:
        if lesson.weekday != slot.weekday:
            continue
        l_start, l_end = _minutes(lesson.start), _minutes(lesson.end)
        span = f"{lesson.start:%H:%M}-{lesson.end:%H:%M}"
        if l_start < end and start < l_end:
            return f"overlaps {lesson.title} ({span})"
        need = travel_minutes(lesson.campus, slot.campus)
        if l_end <= start and start - l_end < need:
            return (f"starts {start - l_end} min after {lesson.title} ends at "
                    f"{lesson.campus}; getting to {slot.campus} takes about {need} min")
        if end <= l_start and l_start - end < need:
            return (f"ends {l_start - end} min before {lesson.title} at "
                    f"{lesson.campus}; getting there takes about {need} min")
    return None


def _minutes(moment: time) -> int:
    return moment.hour * 60 + moment.minute


def upcoming(slots, now: datetime, days_ahead: int) -> list[Occurrence]:
    """Every occurrence of `slots` starting after `now`, within `days_ahead`."""
    local_now = now.astimezone(LONDON)
    horizon = local_now + timedelta(days=days_ahead)
    found = []
    for offset in range(days_ahead + 1):
        day = (local_now + timedelta(days=offset)).date()
        for slot in slots:
            if slot.weekday != day.weekday():
                continue
            start = datetime.combine(day, slot.start, LONDON)
            end = datetime.combine(day, slot.end, LONDON)
            if local_now < start <= horizon:
                found.append(Occurrence(slot, start, end, clash_reason(slot)))
    found.sort(key=lambda o: (o.start, o.slot.title))
    return found


def club_sessions(clubs: list[str], now: datetime, days_ahead: int) -> list[Occurrence]:
    slots = [s for club in clubs for s in CLUB_SESSIONS[club]]
    return upcoming(slots, now, days_ahead)


def campus_events(host: str | None, now: datetime, days_ahead: int) -> list[Occurrence]:
    slots = [e for e in EVENTS if not host or e.host == host]
    return upcoming(slots, now, days_ahead)


def parse_host(text: str | None) -> str | None:
    """`"the union"` -> `"Union"`; empty or "both" -> None (all hosts)."""
    words = (text or "").lower()
    tokens = set(words.replace(",", " ").split())
    if not tokens or tokens & {"both", "all", "any", "either"}:
        return None
    # "Imperial College Union" is the Union, so the Union wins a tie.
    if "union" in words or "icu" in tokens:
        return "Union"
    if "imperial" in words or "college" in words:
        return "Imperial"
    return None

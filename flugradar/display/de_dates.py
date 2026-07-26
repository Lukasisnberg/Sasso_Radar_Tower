"""German weekday/month names, looked up locally instead of via the OS
locale -- nothing in this project calls locale.setlocale(), so
time.strftime("%A"/"%B"/"%a") renders in English regardless of the
device's language setting unless de_DE.UTF-8 happens to be generated on
that particular Pi. A small self-contained table avoids that dependency,
matching the same pattern _WEATHER_CODES already uses for the weather
vocabulary.
"""

WEEKDAYS_FULL = {
    0: "Montag", 1: "Dienstag", 2: "Mittwoch", 3: "Donnerstag",
    4: "Freitag", 5: "Samstag", 6: "Sonntag",
}

WEEKDAYS_SHORT = {
    0: "Mo", 1: "Di", 2: "Mi", 3: "Do", 4: "Fr", 5: "Sa", 6: "So",
}

MONTHS = {
    1: "Januar", 2: "Februar", 3: "März", 4: "April", 5: "Mai", 6: "Juni",
    7: "Juli", 8: "August", 9: "September", 10: "Oktober", 11: "November", 12: "Dezember",
}


def weekday_full(tm_wday: int) -> str:
    """tm_wday: 0=Monday..6=Sunday, as returned by time.struct_time."""
    return WEEKDAYS_FULL[tm_wday]


def weekday_short(tm_wday: int) -> str:
    return WEEKDAYS_SHORT[tm_wday]


def month_name(tm_mon: int) -> str:
    """tm_mon: 1=January..12=December, as returned by time.struct_time."""
    return MONTHS[tm_mon]

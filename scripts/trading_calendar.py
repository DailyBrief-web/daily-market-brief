"""
Sprawdza czy dany dzien byl dniem sesyjnym na gieldach USA i/lub GPW.
Lista swiat jest utrzymywana recznie - trzeba ja aktualizowac raz w roku
(np. na stronie NYSE / GPW publikowany jest kalendarz sesji na kolejny rok).
"""
from datetime import date

# Swieta gieldowe NYSE 2026 (przyblizone, do weryfikacji na nyse.com)
NYSE_HOLIDAYS_2026 = {
    "2026-01-01", "2026-01-19", "2026-02-16", "2026-04-03",
    "2026-05-25", "2026-06-19", "2026-07-03", "2026-09-07",
    "2026-11-26", "2026-12-25",
}

# Swieta gieldowe GPW 2026 (przyblizone, do weryfikacji na gpw.pl)
GPW_HOLIDAYS_2026 = {
    "2026-01-01", "2026-01-06", "2026-04-03", "2026-04-06",
    "2026-05-01", "2026-05-03", "2026-06-04", "2026-08-15",
    "2026-11-01", "2026-11-11", "2026-12-25", "2026-12-26",
}


def is_trading_day(d: date, market: str = "nyse") -> bool:
    """market: 'nyse' albo 'gpw'"""
    if d.weekday() >= 5:  # sobota / niedziela
        return False
    key = d.isoformat()
    holidays = NYSE_HOLIDAYS_2026 if market == "nyse" else GPW_HOLIDAYS_2026
    return key not in holidays


def session_status(d: date) -> dict:
    """Zwraca informacje o tym, ktore rynki mialy dzis sesje."""
    return {
        "us_open": is_trading_day(d, "nyse"),
        "gpw_open": is_trading_day(d, "gpw"),
    }

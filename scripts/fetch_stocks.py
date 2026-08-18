"""
Pobiera ostatnia cene i zmiane % dla listy tickerow z Finnhub
(oficjalne darmowe API z kluczem, w przeciwienstwie do Stooq/Yahoo dziala
niezawodnie z serwerow w chmurze typu GitHub Actions - te dwa poprzednie
darmowe zrodla bez klucza blokowaly zapytania z chmury).

Wymaga zmiennej srodowiskowej FINNHUB_API_KEY (darmowy klucz z finnhub.io/register).
Darmowy tier: 60 zapytan/minute, co w zupelnosci wystarcza do ~40 tickerow raz dziennie.

UWAGA: darmowy tier Finnhub najpewniej dziala dla spolek notowanych w USA (w tym
ADR-y takich firm jak ASML, TSM, SAP, BABA, NVO, AZN, TM - one wszystkie maja
notowania na gieldach amerykanskich). Symbole notowane WYLACZNIE na gieldach
pozaamerykanskich (np. londynskie ETF-y, paryskie/szwajcarskie akcje) moga nie
byc dostepne na darmowym planie - wtedy po prostu znikaja z wyniku (bez bledu
calego skryptu), warto to zweryfikowac i ew. podmienic na amerykanskie odpowiedniki.
"""
import json
import time
import urllib.request
import os

# Twoje akcje - tickery Finnhub (przewaznie identyczne z popularnymi symbolami)
MY_STOCK_SYMBOLS = {
    "NVDA": "NVDA", "ASML": "ASML", "AMD": "AMD", "OSCR": "OSCR",
    "ZPRD": "ZPRD", "AMZN": "AMZN", "CNDX": None, "ELF": "ELF",
    "NOW": "NOW", "SXRS": None, "IBCJ": None, "GOOG": "GOOG",
    "TTWO": "TTWO", "BTC": "BINANCE:BTCUSDT", "META": "META", "SOFI": "SOFI",
}

WORLD_STOCK_SYMBOLS = {
    "TSM": "TSM", "SMSN": None, "MC": None, "NVO": "NVO",
    "NESN": None, "TM": "TM", "SAP": "SAP", "BABA": "BABA",
    "AZN": "AZN", "AAPL": "AAPL", "MSFT": "MSFT", "TSLA": "TSLA",
    "AVGO": "AVGO", "LLY": "LLY", "JPM": "JPM", "WMT": "WMT",
    "PLTR": "PLTR", "NFLX": "NFLX", "ORCL": "ORCL", "COST": "COST",
}

# Indeksy nie sa dostepne na darmowym planie Finnhub - uzywamy ETF-ow
# sledzacych te same indeksy jako wiarygodnego przyblizenia.
INDEX_PROXIES = {
    "S&P 500": "SPY",
    "NASDAQ": "QQQ",
    "Dow Jones": "DIA",
}

BASE_URL = "https://finnhub.io/api/v1/quote"


def _fetch_quote(symbol: str, api_key: str, tries: int = 2):
    url = f"{BASE_URL}?symbol={symbol}&token={api_key}"
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            # Finnhub zwraca c=0 dla nieznanych/niedostepnych symboli
            if data.get("c") not in (None, 0):
                return data
        except Exception:
            pass
        time.sleep(1)
    return None


def _fmt_price(value: float) -> str:
    return f"${value:,.2f}"


def _fetch_group(symbol_map: dict, api_key: str) -> dict:
    out = {}
    for our_symbol, finnhub_symbol in symbol_map.items():
        if not finnhub_symbol:
            continue  # brak wiarygodnego mapowania - pomijamy
        quote = _fetch_quote(finnhub_symbol, api_key)
        if not quote:
            continue
        current = quote["c"]
        pct = quote.get("dp", 0)
        sign = "+" if pct >= 0 else ""
        out[our_symbol] = {
            "change": f"{sign}{pct:.2f}%",
            "price": _fmt_price(current),
        }
        time.sleep(1.1)  # limit Finnhub free: 60/min -> ok. 1 zapytanie/sekunde
    return out


def fetch_all_stocks(symbols: list[str]) -> dict:
    """Zachowuje ten sam interfejs co poprzednie wersje (lista symboli) -
    lista jest ignorowana na rzecz wewnetrznych map (MY/WORLD), bo Finnhub
    wymaga osobnego mapowania na jego wlasne tickery."""
    api_key = os.environ.get("FINNHUB_API_KEY")
    if not api_key:
        raise RuntimeError("Brak FINNHUB_API_KEY w zmiennych srodowiskowych")

    if set(symbols) <= set(MY_STOCK_SYMBOLS.keys()):
        return _fetch_group(MY_STOCK_SYMBOLS, api_key)
    return _fetch_group(WORLD_STOCK_SYMBOLS, api_key)


def fetch_indices() -> list[dict]:
    api_key = os.environ.get("FINNHUB_API_KEY")
    if not api_key:
        raise RuntimeError("Brak FINNHUB_API_KEY w zmiennych srodowiskowych")

    out = []
    for name, proxy_symbol in INDEX_PROXIES.items():
        quote = _fetch_quote(proxy_symbol, api_key)
        if not quote:
            continue
        current = quote["c"]
        pct = quote.get("dp", 0)
        sign = "+" if pct >= 0 else ""
        out.append({
            "name": name,
            "value": f"{current:,.2f}",
            "change": f"{sign}{pct:.2f}%",
            "type": "up" if pct >= 0 else "down",
        })
        time.sleep(1.1)
    return out


if __name__ == "__main__":
    key = os.environ.get("FINNHUB_API_KEY")
    if not key:
        print("Ustaw zmienna FINNHUB_API_KEY przed testem.")
    else:
        print(json.dumps(_fetch_group(MY_STOCK_SYMBOLS, key), indent=2, ensure_ascii=False))

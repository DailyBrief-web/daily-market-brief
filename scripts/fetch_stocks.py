"""
Pobiera ostatnia cene zamkniecia i zmiane % dla listy tickerow z Yahoo Finance
(darmowe, bez klucza API, dziala z serwerow w chmurze - w przeciwienstwie do
Stooq, ktory blokuje zakresy IP dostawcow chmurowych takich jak GitHub Actions).

Dla kazdego symbolu pobieramy krotka historie dzienna i liczymy zmiane %
miedzy dwoma ostatnimi sesjami.

Jesli jakis symbol nie mapuje sie poprawnie (np. spolka spoza USA notowana
na innej gieldzie), trzeba poprawic YAHOO_MAP ponizej - w tej wersji sa to
mapowania "najlepszego przyblizenia", warto zweryfikowac na finance.yahoo.com
przed pierwszym uruchomieniem.
"""
import json
import time
import urllib.request

YAHOO_MAP = {
    # Twoje akcje
    "NVDA": "NVDA", "ASML": "ASML", "AMD": "AMD", "OSCR": "OSCR",
    "ZPRD": "ZPRD.L", "AMZN": "AMZN", "CNDX": "CNDX.L", "ELF": "ELF",
    "NOW": "NOW", "SXRS": "SXRS.DE", "IBCJ": "IBCJ.L", "GOOG": "GOOG",
    "TTWO": "TTWO", "BTC": "BTC-USD", "META": "META", "SOFI": "SOFI",
    # Spolki swiatowe
    "TSM": "TSM", "SMSN": "SMSN.L", "MC": "MC.PA", "NVO": "NVO",
    "NESN": "NESN.SW", "TM": "TM", "SAP": "SAP", "BABA": "BABA",
    "AZN": "AZN", "AAPL": "AAPL", "MSFT": "MSFT", "TSLA": "TSLA",
    "AVGO": "AVGO", "LLY": "LLY", "JPM": "JPM", "WMT": "WMT",
    "PLTR": "PLTR", "NFLX": "NFLX", "ORCL": "ORCL", "COST": "COST",
}

INDEX_MAP = {
    "S&P 500": "^GSPC",
    "NASDAQ": "^IXIC",
    "Dow Jones": "^DJI",
    "WIG20": "WIG20.WA",
}

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}


def _fetch_chart(yahoo_symbol: str, tries: int = 3):
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{yahoo_symbol}"
        f"?range=5d&interval=1d"
    )
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers=_HEADERS)
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            result = data.get("chart", {}).get("result")
            if not result:
                time.sleep(2 * (attempt + 1))
                continue
            closes = result[0]["indicators"]["quote"][0]["close"]
            closes = [c for c in closes if c is not None]
            currency = result[0].get("meta", {}).get("currency", "USD")
            if len(closes) >= 2:
                return closes, currency
        except Exception:
            time.sleep(2 * (attempt + 1))
    return None, None


_CURRENCY_SYMBOL = {
    "USD": "$", "EUR": "€", "GBP": "£", "GBp": "£", "CHF": "CHF ",
    "JPY": "¥", "KRW": "₩", "PLN": "zł",
}


def _fmt_price(value: float, currency: str) -> str:
    symbol = _CURRENCY_SYMBOL.get(currency, currency + " ")
    return f"{symbol}{value:,.2f}"


def fetch_change_and_price(symbol: str, yahoo_symbol: str):
    closes, currency = _fetch_chart(yahoo_symbol)
    if not closes:
        return None
    last_close = closes[-1]
    prev_close = closes[-2]
    if prev_close == 0:
        return None
    pct = (last_close - prev_close) / prev_close * 100
    sign = "+" if pct >= 0 else ""
    return {
        "change": f"{sign}{pct:.2f}%",
        "price": _fmt_price(last_close, currency),
    }


def fetch_all_stocks(symbols: list[str]) -> dict:
    out = {}
    for sym in symbols:
        yahoo_symbol = YAHOO_MAP.get(sym)
        if not yahoo_symbol:
            continue
        result = fetch_change_and_price(sym, yahoo_symbol)
        if result:
            out[sym] = result
        time.sleep(0.3)  # uprzejmosc wobec darmowego API
    return out


def fetch_indices() -> list[dict]:
    out = []
    for name, sym in INDEX_MAP.items():
        closes, _ = _fetch_chart(sym)
        if not closes:
            continue
        last_close = closes[-1]
        prev_close = closes[-2]
        if prev_close == 0:
            continue
        pct = (last_close - prev_close) / prev_close * 100
        sign = "+" if pct >= 0 else ""
        out.append({
            "name": name,
            "value": f"{last_close:,.2f}",
            "change": f"{sign}{pct:.2f}%",
            "type": "up" if pct >= 0 else "down",
        })
        time.sleep(0.3)
    return out


if __name__ == "__main__":
    data = fetch_all_stocks(list(YAHOO_MAP.keys()))
    print(json.dumps(data, indent=2, ensure_ascii=False))

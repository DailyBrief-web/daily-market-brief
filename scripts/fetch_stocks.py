"""
Pobiera ostatnia cene zamkniecia i zmiane % dla listy tickerow ze Stooq
(darmowe, bez klucza API). Dla kazdego symbolu pobieramy krotka historie
dzienna i liczymy zmiane % miedzy dwoma ostatnimi sesjami.

Jesli jakis symbol nie mapuje sie poprawnie na Stooq (np. spolka spoza
USA notowana na innej gieldzie), trzeba poprawic STOOQ_MAP ponizej -
w tej wersji sa to mapowania "najlepszego przyblizenia", niektore mogly
sie zmienic - warto zweryfikowac na stooq.com/q/ przed pierwszym uruchomieniem.
"""
import csv
import io
import time
import urllib.request

STOOQ_MAP = {
    # Twoje akcje
    "NVDA": "nvda.us", "ASML": "asml.us", "AMD": "amd.us", "OSCR": "oscr.us",
    "ZPRD": "zprd.us", "AMZN": "amzn.us", "CNDX": "cndx.uk", "ELF": "elf.us",
    "NOW": "now.us", "SXRS": "sxrs.uk", "IBCJ": "ibcj.uk", "GOOG": "goog.us",
    "TTWO": "ttwo.us", "BTC": "btcusd", "META": "meta.us", "SOFI": "sofi.us",
    # Spolki swiatowe
    "TSM": "tsm.us", "SMSN": "smsn.uk", "MC": "mc.fr", "NVO": "nvo.us",
    "NESN": "nesn.sw", "TM": "tm.us", "SAP": "sap.us", "BABA": "baba.us",
    "AZN": "azn.us", "AAPL": "aapl.us", "MSFT": "msft.us", "TSLA": "tsla.us",
    "AVGO": "avgo.us", "LLY": "lly.us", "JPM": "jpm.us", "WMT": "wmt.us",
    "PLTR": "pltr.us", "NFLX": "nflx.us", "ORCL": "orcl.us", "COST": "cost.us",
}

INDEX_MAP = {
    "S&P 500": "^spx",
    "NASDAQ": "^ndq",
    "Dow Jones": "^dji",
    "WIG20": "^wig20",
}


def _fetch_daily_series(stooq_symbol: str, tries: int = 3):
    url = f"https://stooq.com/q/d/l/?s={stooq_symbol}&i=d"
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=10) as resp:
                text = resp.read().decode("utf-8")
            rows = list(csv.DictReader(io.StringIO(text)))
            if len(rows) >= 2:
                return rows
        except Exception:
            time.sleep(1)
    return None


def _fmt_price(value: float, currency_hint: str = "$") -> str:
    return f"{currency_hint}{value:,.2f}"


def fetch_change_and_price(symbol: str, stooq_symbol: str, currency_hint="$"):
    rows = _fetch_daily_series(stooq_symbol)
    if not rows:
        return None
    last = rows[-1]
    prev = rows[-2]
    try:
        last_close = float(last["Close"])
        prev_close = float(prev["Close"])
    except (KeyError, ValueError):
        return None
    if prev_close == 0:
        return None
    pct = (last_close - prev_close) / prev_close * 100
    sign = "+" if pct >= 0 else ""
    return {
        "change": f"{sign}{pct:.2f}%",
        "price": _fmt_price(last_close, currency_hint),
    }


def fetch_all_stocks(symbols: list[str]) -> dict:
    out = {}
    for sym in symbols:
        stooq_symbol = STOOQ_MAP.get(sym)
        if not stooq_symbol:
            continue
        result = fetch_change_and_price(sym, stooq_symbol)
        if result:
            out[sym] = result
        time.sleep(0.3)  # uprzejmosc wobec darmowego API
    return out


def fetch_indices() -> list[dict]:
    out = []
    for name, sym in INDEX_MAP.items():
        rows = _fetch_daily_series(sym)
        if not rows or len(rows) < 2:
            continue
        last, prev = rows[-1], rows[-2]
        try:
            last_close = float(last["Close"])
            prev_close = float(prev["Close"])
        except (KeyError, ValueError):
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
    import json
    data = fetch_all_stocks(list(STOOQ_MAP.keys()))
    print(json.dumps(data, indent=2, ensure_ascii=False))

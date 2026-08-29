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
import urllib.error
import os

# Twoje akcje - tickery Finnhub (przewaznie identyczne z popularnymi symbolami)
MY_STOCK_SYMBOLS = {
    "NVDA": "NVDA", "ASML": "ASML", "AMD": "AMD", "OSCR": "OSCR",
    "ZPRD": "ZPRD", "AMZN": "AMZN", "CNDX": None, "ELF": "ELF",
    "NOW": "NOW", "SXRS": None, "IBCJ": None, "GOOG": "GOOG",
    "TTWO": "TTWO", "BTC": "BINANCE:BTCUSDT", "XRP": "BINANCE:XRPUSDT",
    "META": "META", "SOFI": "SOFI",
}

WORLD_STOCK_SYMBOLS = {
    "TSM": "TSM", "SMSN": None, "MC": None, "NVO": "NVO",
    "NESN": None, "TM": "TM", "SAP": "SAP", "BABA": "BABA",
    "AZN": "AZN", "AAPL": "AAPL", "MSFT": "MSFT", "TSLA": "TSLA",
    "AVGO": "AVGO", "LLY": "LLY", "JPM": "JPM", "WMT": "WMT",
    "PLTR": "PLTR", "NFLX": "NFLX", "ORCL": "ORCL", "COST": "COST",
}

# Nazwy indeksow, o ktore pytamy Gemini (z wlaczonym wyszukiwaniem w internecie -
# patrz fetch_indices() i _ask_gemini_for_index() nizej). Nie probujemy juz
# pobierac ich z Finnhub, bo darmowy plan i tak zwykle ich nie obejmuje.
INDEX_SYMBOLS = {
    "S&P 500": None,
    "NASDAQ": None,
    "WIG20": None,
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


GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-3.6-flash:generateContent?key={api_key}"
)


def _ask_gemini_for_index(name: str, gemini_api_key: str):
    """Ostatnia linia obrony, gdy Finnhub nie ma danych dla danego indeksu.
    WAZNE: model NIE zgaduje - pytamy go z wlaczonym narzedziem wyszukiwania
    w Google (google_search), wiec faktycznie sprawdza aktualne zrodla w
    internecie zamiast halucynowac liczbe. Jesli nie znajdzie wiarygodnych
    danych, ma zwrocic null zamiast czegokolwiek zmyslac."""
    prompt = f"""Wyszukaj w internecie AKTUALNA wartosc zamkniecia dzisiejszej
sesji gieldowej dla indeksu "{name}" oraz procentowa zmiane wzgledem
poprzedniej sesji. Uzyj wyszukiwarki, nie zgaduj i nie szacuj z pamieci.
Jesli nie znajdziesz wiarygodnych, aktualnych danych - zwroc null w obu polach.
Zwroc WYLACZNIE czysty JSON (bez markdown, bez ```), w formacie:
{{"value": <liczba lub null>, "change_pct": <liczba, dodatnia lub ujemna, lub null>}}"""

    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "tools": [{"google_search": {}}],
        "generationConfig": {"temperature": 0.0},
    }).encode("utf-8")

    req = urllib.request.Request(
        GEMINI_URL.format(api_key=gemini_api_key),
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            result = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as err:
        # Blad HTTP (np. zla nazwa narzedzia, niedozwolony model, zly klucz) -
        # cialo odpowiedzi zwykle zawiera dokladny powod, wypisujemy go.
        body_text = err.read().decode("utf-8", errors="replace")
        print(f"UWAGA (indeks '{name}'): Gemini HTTP {err.code}: {body_text[:500]}")
        return None
    except Exception as err:
        print(f"UWAGA (indeks '{name}'): blad polaczenia z Gemini: {err}")
        return None

    try:
        text = result["candidates"][0]["content"]["parts"][0]["text"].strip()
    except (KeyError, IndexError) as err:
        print(f"UWAGA (indeks '{name}'): nieoczekiwana struktura odpowiedzi Gemini: {err}")
        print(f"Pelna odpowiedz: {json.dumps(result, ensure_ascii=False)[:800]}")
        return None

    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    try:
        data = json.loads(text)
    except json.JSONDecodeError as err:
        print(f"UWAGA (indeks '{name}'): odpowiedz Gemini nie jest poprawnym JSON: {err}")
        print(f"Otrzymany tekst: {text[:500]}")
        return None

    if data.get("value") is None:
        print(f"INFO (indeks '{name}'): Gemini nie znalazlo wiarygodnych danych (value=null).")
        return None
    return data


def fetch_indices() -> list[dict]:
    """Indeksy pobieramy bezposrednio przez Gemini z wlaczonym wyszukiwaniem -
    Finnhub na darmowym planie i tak zwykle nie ma indeksow, wiec pomijamy ten
    krok i pytamy od razu, zeby nie tracic czasu na próbę, która i tak
    najczesciej zawiedzie."""
    gemini_key = os.environ.get("GEMINI_API_KEY")
    if not gemini_key:
        raise RuntimeError("Brak GEMINI_API_KEY w zmiennych srodowiskowych")

    out = []
    for name in INDEX_SYMBOLS.keys():
        fallback = _ask_gemini_for_index(name, gemini_key)
        if not fallback:
            continue  # Gemini nie znalazlo wiarygodnych danych - pomijamy
        current = fallback["value"]
        pct = fallback.get("change_pct") or 0
        sign = "+" if pct >= 0 else ""
        out.append({
            "name": name,
            "value": f"{current:,.2f}",
            "change": f"{sign}{pct:.2f}%",
            "type": "up" if pct >= 0 else "down",
        })
    return out


if __name__ == "__main__":
    key = os.environ.get("FINNHUB_API_KEY")
    if not key:
        print("Ustaw zmienna FINNHUB_API_KEY przed testem.")
    else:
        print(json.dumps(_fetch_group(MY_STOCK_SYMBOLS, key), indent=2, ensure_ascii=False))

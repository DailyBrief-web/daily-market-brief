"""
Glowny skrypt - uruchamiany codziennie przez GitHub Actions.

1. Sprawdza czy dzisiaj byla sesja na NYSE / GPW.
2. Jesli tak - pobiera kursy akcji, indeksy i newsy, zapisuje data/YYYY-MM-DD.json.
3. Jesli nie - zapisuje "pusty" brief z flaga tradingDay=false (gieldy zamkniete).
4. Aktualizuje data/manifest.json, ktory frontend uzywa do zbudowania kalendarza
   (lista dat, dla ktorych istnieja zapisane dane).
"""
import json
import os
import re
from datetime import date, datetime

from fetch_news import build_news_sections
from fetch_stocks import fetch_all_stocks, fetch_indices
from trading_calendar import session_status

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")

MY_STOCK_LIST = ['ASML','AMD','NVDA','OSCR','ZPRD','AMZN','CNDX','ELF','NOW',
                  'SXRS','IBCJ','GOOG','TTWO','BTC','XRP','META','SOFI']
WORLD_STOCK_LIST = ['TSM','SMSN','MC','NVO','NESN','TM','SAP','BABA','AZN','AAPL',
                     'MSFT','TSLA','AVGO','LLY','JPM','WMT','PLTR','NFLX','ORCL','COST']


def build_title(status: dict) -> str:
    if not status["us_open"] and not status["gpw_open"]:
        return "Gieldy zamkniete — brak dzisiejszej sesji"
    return "Podsumowanie dzisiejszej sesji"


def first_sentence(text: str) -> str:
    """Wyciaga pierwsze pelne zdanie z tekstu - uzywane do tytulu, zeby nie
    ucinac w polowie slowa i nie doklejac wielokropka."""
    match = re.match(r"^.*?[.!?](?=\s|$)", text)
    return match.group(0).strip() if match else text.strip()


def load_existing_brief(date_str: str) -> dict | None:
    """Jesli plik na dzisiaj juz istnieje (np. z poprzedniej proby), wczytaj go -
    pozwala to na dopelnienie tylko brakujacych czesci zamiast nadpisywania calosci."""
    path = os.path.join(DATA_DIR, f"{date_str}.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def is_empty(value) -> bool:
    return value is None or value == {} or value == []


def build_brief_for_today() -> dict:
    today = date.today()
    today_str = today.isoformat()
    status = session_status(today)
    is_trading_day = status["us_open"] or status["gpw_open"]

    existing = load_existing_brief(today_str)

    # Skrot: jesli WSZYSTKO juz kompletne (rozne kryteria kompletnosci dla
    # dnia sesyjnego i dnia bez sesji), nic wiecej nie rob.
    if is_trading_day:
        already_complete = bool(
            existing and existing.get("tradingDay")
            and not is_empty(existing.get("marketNews"))
            and not is_empty(existing.get("myStocks"))
            and not is_empty(existing.get("indices"))
        )
    else:
        already_complete = bool(
            existing and existing.get("tradingDay") is False
            and not is_empty(existing.get("politicaUS"))
            and not is_empty(existing.get("politicaPolska"))
        )
    if already_complete:
        print("Dzisiejszy brief jest juz kompletny - nic do zrobienia.")
        return existing

    # POLITYKA I GOSPODARKA - pobieramy ZAWSZE, niezaleznie od tego czy dzis
    # jest sesja gieldowa. Wydarzenia polityczne/gospodarcze nie sa zwiazane
    # z otwarciem gieldy - w weekend tez moga zapasc wazne decyzje (np.
    # oswiadczenie prezydenta, decyzja rzadu, umowa miedzynarodowa).
    has_existing_news = bool(
        existing and not is_empty(existing.get("politicaUS", []))
        and not is_empty(existing.get("politicaPolska", []))
    )
    if has_existing_news:
        news = {k: existing.get(k, []) for k in [
            "politicaUS", "politicaPolska", "politicaEurope",
            "economyUS", "economyEU", "economyIntl", "marketNews",
        ]}
        print("Newsy z poprzedniej proby juz sa - pomijam ponowne pobieranie.")
    else:
        try:
            news = build_news_sections()
        except Exception as err:
            print(f"UWAGA: nie udalo sie pobrac/podsumowac newsow: {err}")
            news = {}

    if not is_trading_day:
        # Bez sesji gieldowej nie ma kursow/indeksow do pobrania - te po
        # prostu nie istnieja tego dnia. Sekcja "Wiadomosci rynkowe" tez
        # zostaje jako wyrazne info o braku sesji, a nie realne newsy o
        # spolkach (ktore z natury sa zwiazane z notowaniami).
        my_stocks, world_stocks, indices = {}, {}, []
        title = "Gieldy zamkniete — brak dzisiejszej sesji"
        title_source = None
        market_news = ["Dzisiaj nie ma sesji gieldowej (weekend lub swieto)."]
    else:
        if existing and not is_empty(existing.get("myStocks")):
            my_stocks = existing["myStocks"]
            print("Kursy 'moich akcji' z poprzedniej proby juz sa - pomijam.")
        else:
            try:
                my_stocks = fetch_all_stocks(MY_STOCK_LIST)
            except Exception as err:
                print(f"UWAGA: nie udalo sie pobrac 'moich akcji': {err}")
                my_stocks = {}

        if existing and not is_empty(existing.get("worldStocks")):
            world_stocks = existing["worldStocks"]
            print("Kursy spolek swiatowych z poprzedniej proby juz sa - pomijam.")
        else:
            try:
                world_stocks = fetch_all_stocks(WORLD_STOCK_LIST)
            except Exception as err:
                print(f"UWAGA: nie udalo sie pobrac swiatowych spolek: {err}")
                world_stocks = {}

        if existing and not is_empty(existing.get("indices")):
            indices = existing["indices"]
            print("Indeksy z poprzedniej proby juz sa - pomijam.")
        else:
            try:
                indices = fetch_indices()
            except Exception as err:
                print(f"UWAGA: nie udalo sie pobrac indeksow: {err}")
                indices = []

        market_news = news.get("marketNews", [])
        if market_news:
            title = first_sentence(market_news[0])
            title_source = "💼 Giełda — Wiadomości rynkowe"
        else:
            title = build_title(status)
            title_source = None

    return {
        "date": today_str,
        "tradingDay": is_trading_day,
        "title": title,
        "titleSource": title_source,
        "politicaUS": news.get("politicaUS", []),
        "politicaPolska": news.get("politicaPolska", []),
        "politicaEurope": news.get("politicaEurope", []),
        "economyUS": news.get("economyUS", []),
        "economyEU": news.get("economyEU", []),
        "economyIntl": news.get("economyIntl", []),
        "indices": indices,
        "myStocks": my_stocks,
        "worldStocks": world_stocks,
        "marketNews": market_news,
    }


def update_manifest(new_date: str, trading_day: bool):
    os.makedirs(DATA_DIR, exist_ok=True)
    manifest_path = os.path.join(DATA_DIR, "manifest.json")
    manifest = {"dates": {}}
    if os.path.exists(manifest_path):
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
    manifest["dates"][new_date] = {"tradingDay": trading_day}
    manifest["lastUpdated"] = datetime.utcnow().isoformat() + "Z"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)


def main():
    brief = build_brief_for_today()
    os.makedirs(DATA_DIR, exist_ok=True)
    out_path = os.path.join(DATA_DIR, f"{brief['date']}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(brief, f, ensure_ascii=False, indent=2)
    update_manifest(brief["date"], brief["tradingDay"])
    print(f"Zapisano {out_path}")


if __name__ == "__main__":
    main()

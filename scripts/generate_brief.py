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
from datetime import date, datetime

from fetch_news import build_news_sections
from fetch_stocks import fetch_all_stocks, fetch_indices, STOOQ_MAP
from trading_calendar import session_status

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")

MY_STOCK_LIST = ['ASML','AMD','NVDA','OSCR','ZPRD','AMZN','CNDX','ELF','NOW',
                  'SXRS','IBCJ','GOOG','TTWO','BTC','META','SOFI']
WORLD_STOCK_LIST = ['TSM','SMSN','MC','NVO','NESN','TM','SAP','BABA','AZN','AAPL',
                     'MSFT','TSLA','AVGO','LLY','JPM','WMT','PLTR','NFLX','ORCL','COST']


def build_title(status: dict) -> str:
    if not status["us_open"] and not status["gpw_open"]:
        return "Gieldy zamkniete — brak dzisiejszej sesji"
    return "Podsumowanie dzisiejszej sesji"


def build_brief_for_today() -> dict:
    today = date.today()
    status = session_status(today)

    if not status["us_open"] and not status["gpw_open"]:
        # Nie ma sesji (weekend / swieto) - nie pobieramy kursow, zapisujemy pusty dzien
        return {
            "date": today.isoformat(),
            "tradingDay": False,
            "title": "Gieldy zamkniete — brak dzisiejszej sesji",
            "politicaUS": [], "politicaPolska": [], "politicaEurope": [],
            "economyUS": [], "economyGlobal": [],
            "indices": [], "myStocks": {}, "worldStocks": {},
            "marketNews": ["Dzisiaj nie ma sesji gieldowej (weekend lub swieto)."],
        }

    news = build_news_sections()
    my_stocks = fetch_all_stocks(MY_STOCK_LIST)
    world_stocks = fetch_all_stocks(WORLD_STOCK_LIST)
    indices = fetch_indices()

    top_market_news = news.get("marketNews", [])
    title = top_market_news[0][:90] + "…" if top_market_news else build_title(status)

    return {
        "date": today.isoformat(),
        "tradingDay": True,
        "title": title,
        "politicaUS": news.get("politicaUS", []),
        "politicaPolska": news.get("politicaPolska", []),
        "politicaEurope": news.get("politicaEurope", []),
        "economyUS": news.get("economyUS", []),
        "economyGlobal": news.get("economyGlobal", []),
        "indices": indices,
        "myStocks": my_stocks,
        "worldStocks": world_stocks,
        "marketNews": top_market_news,
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

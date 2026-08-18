"""
1. Sciaga naglowki + skroty z darmowych kanalow RSS (polityka PL/US/EU, gospodarka, rynki).
2. Wysyla je do darmowego API Gemini z prosba o wyselekcjonowanie najwazniejszych
   wiadomosci i napisanie ich po polsku, min. 5 zdan kazda, w formacie JSON
   pasujacym do struktury strony.

Wymaga zmiennej srodowiskowej GEMINI_API_KEY (darmowy klucz z aistudio.google.com).
"""
import json
import os
import time
import urllib.request
import xml.etree.ElementTree as ET

def _google_news_rss(query: str, lang: str = "pl", country: str = "PL") -> str:
    """Buduje URL do wyszukiwarki Google News RSS - darmowe, stabilne, bez klucza API."""
    from urllib.parse import quote
    return (
        f"https://news.google.com/rss/search?q={quote(query)}"
        f"&hl={lang}&gl={country}&ceid={country}:{lang}"
    )


RSS_FEEDS = {
    "politicaUS": [
        _google_news_rss("Trump White House politics", "en", "US"),
    ],
    "politicaPolska": [
        _google_news_rss("polityka Polska Sejm rząd", "pl", "PL"),
    ],
    "politicaEurope": [
        _google_news_rss("European Union politics", "en", "US"),
    ],
    "economyUS": [
        _google_news_rss("US economy Federal Reserve inflation", "en", "US"),
    ],
    "economyGlobal": [
        _google_news_rss("global economy China EU economy", "en", "US"),
    ],
    "marketNews": [
        _google_news_rss("stock market earnings Wall Street", "en", "US"),
    ],
}

GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-3.6-flash:generateContent?key={api_key}"
)


def _fetch_rss(url: str, limit: int = 8) -> list[str]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read()
        root = ET.fromstring(raw)
        items = []
        for item in root.iter("item"):
            title = item.findtext("title") or ""
            desc = item.findtext("description") or ""
            if title:
                items.append(f"{title.strip()} — {desc.strip()[:200]}")
            if len(items) >= limit:
                break
        return items
    except Exception:
        return []


def collect_raw_headlines() -> dict:
    collected = {}
    for category, feeds in RSS_FEEDS.items():
        headlines = []
        for feed_url in feeds:
            headlines.extend(_fetch_rss(feed_url))
        collected[category] = headlines
    return collected


def summarize_with_gemini(headlines_by_category: dict, api_key: str, tries: int = 4) -> dict:
    """
    Wysyla zebrane naglowki do Gemini i prosi o gotowe, wyselekcjonowane
    wiadomosci po polsku w strukturze zgodnej ze strona.
    """
    prompt = f"""
Jestes redaktorem porannego briefingu finansowego po polsku.
Dostajesz surowe naglowki RSS pogrupowane wg kategorii (ponizej, JSON).
Dla kazdej kategorii wybierz maksymalnie 2 NAJWAZNIEJSZE wiadomosci
(jesli nic waznego - zwroc pusta liste []).

Wymagania:
- Kazda wiadomosc PO POLSKU, MINIMUM 5 zdan, konkretna, bez lania wody.
- Pisz naturalnym jezykiem dziennikarskim, pierwsze zdanie musi streszczac sedno.
- Kategoria "marketNews" (wiadomosci rynkowe / o spolkach): wybierz dokladnie 5 wiadomosci,
  kazda powiazana z konkretnymi spolkami/tickerami jesli to mozliwe.
- Nie wymyslaj faktow ktorych nie ma w zrodlowych naglowkach - jesli czegos brakuje, pomin.

Zrodlowe naglowki:
{json.dumps(headlines_by_category, ensure_ascii=False, indent=2)}

Zwroc WYLACZNIE poprawny JSON w formacie:
{{
  "politicaUS": ["..."],
  "politicaPolska": ["..."],
  "politicaEurope": ["..."],
  "economyUS": ["..."],
  "economyGlobal": ["..."],
  "marketNews": ["...", "...", "...", "...", "..."]
}}
"""
    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.4, "responseMimeType": "application/json"},
    }).encode("utf-8")

    req = urllib.request.Request(
        GEMINI_URL.format(api_key=api_key),
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    last_error = None
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=45) as resp:
                result = json.loads(resp.read().decode("utf-8"))
            text = result["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(text)
        except Exception as err:
            last_error = err
            time.sleep(5 + attempt * 10)  # 5s, 15s, 25s, 35s - coraz dluzsza przerwa

    raise RuntimeError(f"Gemini nie odpowiedział po {tries} probach: {last_error}")


def build_news_sections() -> dict:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("Brak GEMINI_API_KEY w zmiennych srodowiskowych")
    headlines = collect_raw_headlines()
    return summarize_with_gemini(headlines, api_key)


if __name__ == "__main__":
    print(json.dumps(build_news_sections(), indent=2, ensure_ascii=False))

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
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

def _google_news_rss(query: str, lang: str = "pl", country: str = "PL") -> str:
    """Buduje URL do wyszukiwarki Google News RSS - darmowe, stabilne, bez klucza API.
    Dodajemy 'when:1d', zeby Google zwracal TYLKO artykuly z ostatnich 24h -
    bez tego wyszukiwarka zwraca tez starsze, wciaz "trafne" tematycznie
    artykuly (np. analizy sprzed kilku dni), co psuje swiezosc briefu."""
    from urllib.parse import quote
    query_with_freshness = f"{query} when:1d"
    return (
        f"https://news.google.com/rss/search?q={quote(query_with_freshness)}"
        f"&hl={lang}&gl={country}&ceid={country}:{lang}"
    )


RSS_FEEDS = {
    "politicaUS": [
        _google_news_rss("Trump White House politics", "en", "US"),
        _google_news_rss("US Congress legislation vote", "en", "US"),
    ],
    "politicaPolska": [
        _google_news_rss("polityka Polska Sejm rząd", "pl", "PL"),
        _google_news_rss("Polska rząd decyzja ustawa", "pl", "PL"),
        _google_news_rss("Tusk rząd konferencja", "pl", "PL"),
    ],
    "politicaEurope": [
        _google_news_rss("European Union politics", "en", "US"),
        _google_news_rss("EU Brussels decision policy", "en", "US"),
    ],
    "economyUS": [
        _google_news_rss("US economy Federal Reserve inflation", "en", "US"),
        _google_news_rss("US taxes economy policy", "en", "US"),
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


def _fetch_rss(url: str, limit: int = 20, max_age_hours: int = 30) -> list[str]:
    """Pobiera naglowki, ODRZUCAJAC te starsze niz max_age_hours - to twarda
    gwarancja swiezosci, niezalezna od tego, czy Google poprawnie zastosuje
    filtr 'when:1d' w URL (czasem nie stosuje go idealnie)."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read()
        root = ET.fromstring(raw)
        cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
        items = []
        for item in root.iter("item"):
            title = item.findtext("title") or ""
            desc = item.findtext("description") or ""
            pub_date_raw = item.findtext("pubDate") or ""
            if not title:
                continue
            try:
                pub_date = parsedate_to_datetime(pub_date_raw)
                if pub_date.tzinfo is None:
                    pub_date = pub_date.replace(tzinfo=timezone.utc)
                if pub_date < cutoff:
                    continue  # za stary artykul - pomijamy
            except Exception:
                pass  # brak/bledna data - nie odrzucamy w ciemno, ale tez nie ufamy w 100%
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
Kazda kategoria zawiera naglowki z KILKU roznych zapytan/zrodel - ten sam
temat moze wiec pojawic sie w kilku wariantach/sformulowaniach.

DEFINICJA "WAZNOSCI" (kluczowe, stosuj to konsekwentnie):
Waznosc tematu NIE jest Twoja subiektywna ocena - to CZESTOTLIWOSC, z jaka
dany temat/wydarzenie POWTARZA SIE w roznych naglowkach w obrebie kategorii.
1. Najpierw pogrupuj naglowki wg tego, o jakim konkretnym wydarzeniu mowia
   (np. "decyzja rzadu ws. VAT na paliwo" to jeden temat, nawet jesli opisany
   w 4 roznych naglowkach na 4 rozne sposoby).
2. Temat, ktory pojawia sie w NAJWIECEJ naglowkow (niezaleznie od zrodla/
   zapytania), jest OBIEKTYWNIE najwazniejszy - to znaczy, ze najwiecej
   redakcji/serwisow uznalo go za istotny tego dnia.
3. Wybierz wg tej zasady maksymalnie 2 najczesciej powtarzajace sie tematy
   na kategorie (jesli nic sie nie powtarza - wybierz pojedyncze naglowki
   o najwiekszym znaczeniu faktycznym, np. decyzje rzadowe > deklaracje bez
   konkretow > pojedyncze wypowiedzi).
   Jesli w kategorii nic waznego nie ma - zwroc pusta liste [].

SWIEZOSC (rownie kluczowe):
Naglowki zostaly juz wstepnie odfiltrowane pod katem daty publikacji, ale
mimo to badz czujny - jesli jakis naglowek opisuje wydarzenie, ktore wg
Twojej wiedzy jest OGOLNIE ZNANE od dluzszego czasu (np. "porazka polityczna
X" ktora jest powszechnie komentowana od dawna, a nie z ostatniej doby) -
POMIN go, nawet jesli formalnie przeszedl filtr daty. Priorytet maja
KONKRETNE, SWIEZE wydarzenia z ostatnich 24h (decyzje, glosowania, ogloszenia),
a nie kontynuacje/analizy starszych, juz "oswojonych" tematow.

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

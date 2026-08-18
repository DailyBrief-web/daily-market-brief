# Daily Market Brief — system automatyczny (w 100% darmowy)

## Jak to działa

1. **GitHub Actions** odpala się codziennie o 22:00 UTC w dni robocze (`.github/workflows/daily-brief.yml`).
2. Skrypt (`scripts/generate_brief.py`):
   - sprawdza czy dziś była sesja na NYSE/GPW (`scripts/trading_calendar.py`),
   - jeśli tak — pobiera kursy akcji ze Stooq (`scripts/fetch_stocks.py`) i newsy podsumowane przez Gemini (`scripts/fetch_news.py`),
   - jeśli nie — zapisuje pusty dzień z `tradingDay: false`,
   - zapisuje wynik jako `data/YYYY-MM-DD.json` i aktualizuje `data/manifest.json`.
3. Workflow **commituje i pushuje** nowy plik do repo — to jest Twoje archiwum, raz zapisane, nigdy nie generowane ponownie.
4. **GitHub Pages** hostuje `index.html`, który przy starcie i przy zmianie daty w kalendarzu **fetchuje** odpowiedni plik JSON.

## Setup (jednorazowo, ~15 minut)

1. **Załóż konto na GitHub** (github.com) jeśli jeszcze nie masz.
2. **Utwórz nowe repozytorium**, np. `daily-market-brief` (publiczne — GitHub Pages za darmo wymaga publicznego repo, chyba że masz plan Pro).
3. **Wgraj do niego całą zawartość tego folderu** (przez stronę GitHub — "Add file → Upload files" — albo `git push` jeśli znasz git).
4. **Zdobądź darmowy klucz Gemini API**:
   - wejdź na https://aistudio.google.com/apikey
   - zaloguj się kontem Google, kliknij "Create API key"
   - skopiuj klucz
5. **Dodaj klucz jako sekret w repo**:
   - w repo: Settings → Secrets and variables → Actions → New repository secret
   - Name: `GEMINI_API_KEY`, Value: wklejony klucz
6. **Włącz GitHub Pages**:
   - Settings → Pages → Source: "Deploy from a branch" → branch `main`, folder `/ (root)`
   - po chwili dostaniesz adres typu `https://twoja-nazwa.github.io/daily-market-brief/`
7. **Włącz Actions** (jeśli poprosi o potwierdzenie) i odpal raz ręcznie:
   - zakładka Actions → "Daily Market Brief" → "Run workflow"
   - sprawdź czy w folderze `data/` pojawił się nowy plik z dzisiejszą datą

Od tej pory system działa sam, codziennie. Otwierasz stronę na telefonie (możesz dodać do ekranu głównego — jest już skonfigurowana jako "web app"), a kalendarz na dole pozwala wrócić do dowolnego zapisanego dnia.

## Co warto poprawić / dostroić

- **Mapowanie tickerów na Stooq** (`scripts/fetch_stocks.py`, słownik `STOOQ_MAP`) — kilka spółek spoza USA (np. SMSN, MC, NESN) ma mapowania "najlepszego przybliżenia". Warto zweryfikować symbole na stooq.com przed pierwszym uruchomieniem.
- **Lista świąt giełdowych** (`scripts/trading_calendar.py`) jest wpisana ręcznie na 2026 rok — raz w roku trzeba ją zaktualizować.
- **Źródła RSS** (`scripts/fetch_news.py`) — obecnie kilka dużych zachodnich agencji + PAP. Możesz dorzucić więcej polskich portali (np. Money.pl, Bankier.pl, Parkiet) — każdy ma darmowy RSS.
- **Godzina uruchomienia** w workflow (`cron: '0 22 * * 1-5'`) — 22:00 UTC to ok. północ czasu polskiego latem / 23:00 zimą, czyli już po zamknięciu sesji US. Możesz przesunąć.

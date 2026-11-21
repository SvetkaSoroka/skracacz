# Skracacz linków ze statystyką kliknięć

Projekt na Nowatorski Projekt Indywidualny, semestr zimowy 2026/27.
Autor: Andrii Arbuzov, nr albumu 58686.

Działająca wersja: https://skracacz.adspowerandrew.workers.dev

Użytkownik wkleja długi link i dostaje krótki. Każde kliknięcie w krótki link zapisuje się w bazie: kraj, czas i źródło. Statystykę widać na osobnej stronie. Interfejs strony jest po angielsku.

## Jak to działa

Wszystko jest na Cloudflare. Jeden Worker napisany w Pythonie obsługuje API, przekierowania i zapis kliknięć. Pliki HTML, CSS i JS leżą w folderze `public/` i Cloudflare serwuje je z tego samego Workera (Workers Static Assets). Dane są w bazie Cloudflare D1.

```
przeglądarka  ->  Worker (Python, src/entry.py)  ->  D1 (tabele links i clicks)
                  public/: index.html, stats.html, 404.html
```

Skąd biorę dane o kliknięciu:

| Pole | Skąd |
| --- | --- |
| kraj | `request.cf.country`, Cloudflare dodaje to do każdego żądania |
| czas | czas serwera w UTC w chwili kliknięcia |
| źródło | nagłówek `Referer`, zapisuję tylko domenę (np. `instagram.com`); gdy go nie ma, to „Direct or unknown” |

Nie zapisuję adresów IP ani pełnych adresów, z których ktoś przyszedł.

## Zmiany od etapu I

- Doszedł prywatny klucz. Przy tworzeniu linku API zwraca klucz, a w bazie zapisuję tylko jego hash SHA-256. Bez klucza nie da się zobaczyć statystyki ani usunąć linku. W etapie I każdy, kto znał kod, mógł usunąć cudzy link.
- Statystyka ma dodatkowo rozkład po godzinach (UTC) i listę 15 ostatnich kliknięć.
- Żądania HEAD i prefetch przeglądarki nie liczą się jako kliknięcia.

## API

| Metoda | Ścieżka | Co robi | Klucz |
| --- | --- | --- | --- |
| POST | `/api/links` | tworzy krótki link, zwraca kod i klucz | nie |
| GET | `/{code}` | przekierowanie 302 i zapis kliknięcia | nie |
| GET | `/api/links/{code}` | adres docelowy, data utworzenia, liczba kliknięć | tak |
| GET | `/api/links/{code}/stats` | kliknięcia wg kraju, dnia, godziny i źródła | tak |
| DELETE | `/api/links/{code}` | usuwa link razem z kliknięciami | tak |

Klucz podaje się w nagłówku `Authorization: Bearer <klucz>`.

```
POST /api/links  {"url": "https://example.com/bardzo/dlugi/adres"}
-> 201 {"code": "a7Kx2q", "short_url": "https://.../a7Kx2q", "key": "...", "stats_url": "https://.../stats?code=a7Kx2q#key=..."}
```

Klucz w linku do statystyki jest po znaku `#`, więc przeglądarka nie wysyła go do serwera ani w nagłówku Referer. Strona statystyki czyta go w JavaScripcie i dodaje do zapytania do API.

## Baza danych

Schemat jest w `migrations/0001_init.sql`. Dwie tabele:

- `links`: `code` (klucz główny), `url`, `created_at`, `key_hash`
- `clicks`: `id`, `code`, `clicked_at`, `country`, `referer`

Jest indeks na `clicks(code, clicked_at)`, żeby statystyka jednego linku liczyła się szybko. Statystyki liczę zapytaniami `GROUP BY`, osobnych tabel z agregatami nie ma.

## Struktura

```
src/entry.py        Worker: routing, endpointy, zapis kliknięć
src/utils.py        funkcje bez Cloudflare: sprawdzanie URL, kody, klucze, dni na wykresie
public/             strony (index, stats, 404), style.css, home.js, stats.js
migrations/         schemat bazy D1
tests/test_utils.py testy jednostkowe
tests/smoke.py      test end-to-end przez HTTP
wrangler.jsonc      konfiguracja Workera i bindingi (DB, ASSETS)
```

## Uruchomienie lokalnie

Potrzebne są Node.js, `uv` w wersji 0.13.4 lub nowszej i konto Cloudflare (tylko do wdrożenia).

```bash
npx wrangler d1 migrations apply skracacz --local   # tworzy lokalną bazę
uv run pywrangler dev                               # serwer na http://localhost:8787
```

## Testy

```bash
python3 -m unittest discover -s tests -v                 # 12 testów jednostkowych
python3 tests/smoke.py http://localhost:8787             # 17 sprawdzeń przez HTTP
python3 tests/smoke.py https://skracacz.adspowerandrew.workers.dev
```

Test end-to-end tworzy link, klika w niego, sprawdza statystykę, zły klucz i usuwanie. Na końcu usuwa link, więc nie zostawia śmieci w bazie.

## Wdrożenie

```bash
npx wrangler d1 migrations apply skracacz --remote
uv run pywrangler deploy
```

## Ograniczenia

- Python na Workerach działa przez Pyodide. Pierwsze żądanie po dłuższej przerwie jest wolniejsze (zimny start około 0,5 s).
- Kliknięcie zapisuję przed przekierowaniem, więc przekierowanie czeka na zapis do D1. Przy małym ruchu to nie przeszkadza.
- Boty, które pobierają podgląd linku (np. Telegram, Slack), też liczą się jako kliknięcia. Odfiltrowanie ich po User-Agent zostawiam na kolejny etap.
- Wiele aplikacji mobilnych nie wysyła nagłówka Referer, dlatego część kliknięć ma źródło „Direct or unknown”.

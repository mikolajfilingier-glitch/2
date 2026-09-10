# Licytacje mieszkań — aglomeracja śląska

Codziennie zbiera oferty mieszkań z licytacji komorniczych, aukcji syndyka
i przetargów spółdzielni w 15 miastach aglomeracji, filtruje je i publikuje
jako stronę, którą można otworzyć na dowolnym telefonie — bez logowania,
bez aplikacji, bez Claude.

Wszystko działa na darmowych planach GitHuba. Koszt: 0 zł.

---

## Jak to działa

```
GitHub Actions (codziennie ~7:10)
        │
        ├─ scraper/scrape.py
        │     ├─ pobiera listaprzetargow.pl (15 miast × 3 kategorie)
        │     ├─ pobiera przetargi.adradar.pl (3 kategorie × 4 strony)
        │     ├─ scala duplikaty, odrzuca wg kryteriów, ocenia flagami
        │     └─ zapisuje docs/data.json
        │
        └─ commit + push do repozytorium
                │
        GitHub Pages serwuje docs/index.html
                │
        Telefon: strona czyta data.json i pokazuje listę
```

Strona jest statyczna. Nie ma serwera, bazy danych ani kosztów utrzymania.
Dane odświeżają się przez to, że bot codziennie nadpisuje jeden plik JSON.

---

## Uruchomienie (jednorazowo, ~10 minut)

### 1. Utwórz repozytorium

Wejdź na <https://github.com/new>. Nazwa dowolna, np. `licytacje-slask`.
Ustaw **Public** — GitHub Pages na darmowym planie działa tylko dla
publicznych repozytoriów. Nie dodawaj README (jest już w plikach).

> Publiczne repo oznacza, że kod i lista ofert są widoczne dla każdego,
> kto zna adres. Nie ma tu żadnych Twoich danych osobowych ani haseł, więc
> to bezpieczne — ale jeśli wolisz prywatność, GitHub Pages dla repozytoriów
> prywatnych wymaga planu Pro (4 USD/mies.).

### 2. Wgraj pliki

Na stronie nowego repozytorium kliknij **uploading an existing file**
i przeciągnij całą zawartość tego folderu. Zachowaj strukturę katalogów —
najprościej wrzucić folder `przetargi-app` metodą przeciągnięcia z pulpitu,
GitHub zachowa podfoldery.

Struktura po wgraniu:

```
.github/workflows/zbieraj.yml
docs/index.html
docs/data.json
scraper/scrape.py
scraper/test_parsery.py
scraper/dane_startowe.py
scraper/requirements.txt
README.md
```

### 3. Włącz GitHub Pages

**Settings** → **Pages** → w sekcji *Build and deployment*:

- Source: **Deploy from a branch**
- Branch: **main**, folder: **/docs**
- **Save**

Po 1–2 minutach strona będzie pod adresem:

```
https://TWOJA-NAZWA.github.io/licytacje-slask/
```

Ten link wysyłasz komu chcesz. Działa na każdym telefonie, w każdej
przeglądarce. Warto dodać go do ekranu głównego („Dodaj do ekranu
początkowego” w Safari / „Zainstaluj aplikację” w Chrome) — wygląda
wtedy jak zwykła aplikacja.

### 4. Pozwól botowi zapisywać dane

**Settings** → **Actions** → **General** → sekcja *Workflow permissions*:
wybierz **Read and write permissions** → **Save**.

Bez tego kroku bot zbierze dane, ale nie będzie mógł ich zapisać.

### 5. Uruchom pierwszy przebieg ręcznie

Zakładka **Actions** → **Zbieraj oferty** → **Run workflow**.
Przebieg trwa kilka minut (skrypt czeka 1,5 s między żądaniami, żeby nie
obciążać serwisów). Po zakończeniu odśwież stronę.

Strona ma już wpisane 8 ofert z 10.09.2026, więc pokaże coś od razu —
pierwszy automatyczny przebieg je nadpisze aktualnymi.

---

## Kryteria filtrowania

Zakodowane w `scraper/scrape.py` zgodnie z zasadą: **twardo odrzucaj tylko
to, co ogłoszenie mówi wprost, resztę oznaczaj flagą.**

**Zasięg:** Katowice, Sosnowiec, Chorzów, Bytom, Zabrze, Gliwice, Ruda Śląska,
Świętochłowice, Siemianowice Śląskie, Mysłowice, Dąbrowa Górnicza, Tychy,
Będzin, Piekary Śląskie, Czeladź.

**Ceny:** do 180 000 zł. Wyżej, do 220 000 zł, tylko oferty wyraźnie
ponadprzeciętne (cena za m² co najmniej 25% poniżej mediany puli oraz metraż
od 60 m²) — oznaczone znaczkiem „powyżej progu”. Przeciętna oferta za 200 tys.
jest odrzucana, żeby limit faktycznie działał.

**Odrzucane wprost:**
- ogrzewanie węglowe (samo „ogrzewanie piecowe” nie odrzuca — piec bywa gazowy)
- budynek do rozbiórki, wyłączony z użytkowania, grożący zawaleniem
- brak przyłącza wody lub prądu („odcięte media” to nie to samo — odcięcie
  za długi jest odwracalne i typowe dla mieszkań licytacyjnych)
- udział ułamkowy w **samym lokalu** (udział w częściach wspólnych to
  normalna odrębna własność i nie odrzuca)
- lokale użytkowe, garaże, domy, działki
- termin licytacji minął ponad 3 dni temu

**Nie odrzuca:** zdewastowany lokal, stan do kapitalnego remontu, brak
instalacji wewnętrznych. Przy remoncie od zera to atut cenowy, nie wada.

### Zmiana kryteriów

Edytuj górę pliku `scraper/scrape.py`:

```python
PROG_PODSTAWOWY = 180_000     # zwykły limit
PROG_PERELKI = 220_000        # limit dla ofert ponadprzeciętnych
MIASTA = { ... }              # miasta w zasięgu
```

Po zapisaniu zmiany w GitHubie bot użyje nowych wartości przy następnym
przebiegu. Możesz też odpalić go od razu przyciskiem **Run workflow**.

---

## Ograniczenia — warto znać przed użyciem

**Ulice bywają ukryte.** listaprzetargow.pl pokazuje dokładny adres tylko
posiadaczom płatnego konta. Dla większości ofert z tego źródła zobaczysz
miasto i czasem dzielnicę. Adradar podaje ulicę, ale ma mniejszą pulę bez
wykupionego dostępu. Oferty bez ulicy mają znaczek „niepełne dane”.

**Okolica nie jest oceniana automatycznie.** Ocena „przystanek + sklep +
szkoła w zasięgu spaceru” wymaga API map, które jest płatne. Skrypt nie
zgaduje — zostawia „brak danych” i daje przycisk otwierający okolicę
w Google Maps, gdy adres jest znany.

**Stan budynku oceniany jest ze słów kluczowych w opisie**, nie z realnej
wiedzy o budynku. Pożar, zalanie i dezynfekcja dają czerwoną flagę;
służebność, zagrzybienie, pustostan i legalizacja żółtą; „zadbany”
i „po termomodernizacji” zieloną. Brak wzmianki to „brak danych”, nie zielone
światło. To sito na pierwsze przejrzenie, nie zamiennik oględzin.

**Portale mogą zmienić strukturę stron.** Wtedy skrypt zwróci zero ofert.
Jest na to zabezpieczenie: jeśli przebieg nic nie znajdzie, a wcześniej były
dane, stare dane zostają na miejscu, a na stronie pojawia się czerwony pas
z ostrzeżeniem i datą. Nigdy nie zobaczysz pustej listy udającej, że rynek
jest pusty.

**Rejestr komorniczy nie jest scrapowany.** licytacje.komornik.pl to
aplikacja JavaScriptowa — filtry i stronicowanie nie działają po stronie
serwera. Terminy i stan prawny dla ofert, które trafią na górę listy, trzeba
potwierdzić tam ręcznie. Agregatory potrafią trzymać ogłoszenie po odwołanej
licytacji.

**Oznaczenia są lokalne.** „Obserwuję”, „Do obejrzenia” i „Odrzuć” zapisują
się w pamięci przeglądarki na danym urządzeniu. Ty i druga osoba macie
własne, niezależne oznaczenia — nie widzicie się wzajemnie. Zrobienie
wspólnych wymagałoby backendu z bazą danych, czyli wyjścia z darmowego
statycznego hostingu.

**Cena wywoławcza to nie cena końcowa.** Licytacja może pójść znacznie
wyżej. Lista zawęża rynek do kandydatów — nie podejmuje decyzji zakupowych
i nie zastępuje weryfikacji księgi wieczystej ani oględzin.

---

## Utrzymanie

**Przebieg się nie udał?** Zakładka **Actions** → kliknij czerwony przebieg
→ krok „Zbierz oferty” pokaże logi. Najczęstsze przyczyny: portal odpowiada
403 (blokada botów — zwykle mija sama) albo zmienił układ HTML (trzeba
poprawić parser).

**GitHub usypia crona.** W repozytoriach bez aktywności przez 60 dni GitHub
wyłącza zaplanowane workflowy i wysyła maila. Wystarczy wtedy wejść w Actions
i kliknąć **Enable workflow**.

**Testy.** `python scraper/test_parsery.py` sprawdza 41 przypadków parsowania
i filtrowania na prawdziwych fragmentach ogłoszeń, bez ruszania sieci.
Workflow uruchamia je przed każdym zbieraniem — jeśli testy padną, zbieranie
się nie zacznie i stare dane zostaną nietknięte.

**Praca lokalna:**

```bash
pip install -r scraper/requirements.txt
python scraper/test_parsery.py     # testy
python scraper/scrape.py           # przebieg zbierania
python -m http.server -d docs      # podgląd strony na localhost:8000
```

"""
Wypełnia docs/data.json ofertami znalezionymi ręcznie 10.09.2026,
żeby strona miała co pokazać przed pierwszym automatycznym przebiegiem.
Uruchom raz:  python scraper/dane_startowe.py
Późniejsze przebiegi scrape.py nadpiszą te dane własnymi.
"""

import json
import datetime as dt
from dataclasses import asdict
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))
from scrape import Oferta, DATA_FILE, PROG_PODSTAWOWY, PROG_PERELKI, klucz_sortowania  # noqa: E402

DZIS = "2026-09-10"

oferty = [
    Oferta(
        id="seed-kochlowice-tunkla",
        zrodlo="przetargi.adradar.pl",
        link="https://przetargi.adradar.pl/przetarg/mieszkania/Koch%C5%82owice/licytacje_komornicze/17546215",
        pierwsze_wykrycie=DZIS,
        adres="ul. Tunkla",
        miasto="Ruda Śląska",
        dzielnica="Kochłowice",
        cena_wywolawcza=130000,
        metraz=53.0,
        pokoje=2,
        data_licytacji="2026-09-10",
        typ_postepowania="licytacja komornicza",
        stan_prawny_uwagi=(
            "Druga licytacja — cena wywoławcza to 2/3 oszacowania, czyli przy wyższej "
            "cenie nikt lokalu nie kupił. Udział dotyczy części wspólnych budynku "
            "i gruntu, więc przedmiotem jest cały lokal."
        ),
        flaga_budynek={"poziom": "brak", "powod": "Ogłoszenie nie opisuje stanu budynku."},
        flaga_okolica={"poziom": "zielona", "powod": "Ul. Tunkla w Kochłowicach: sklepy spożywcze i usługi na miejscu, Biedronka przy Radoszowskiej, zwykła zabudowa osiedlowa."},
        notatka="2453 zł/m²; druga licytacja obniżyła próg wejścia; sprawdzić powód niepowodzenia pierwszej",
        opis="Lokal mieszkalny stanowiący odrębną nieruchomość wraz z udziałem w części wspólnej, ul. Tunkla, 41-707 Ruda Śląska. Druga licytacja w trybie elektronicznym.",
    ),
    Oferta(
        id="seed-bytom-ruda-121m",
        zrodlo="listaprzetargow.pl",
        link="https://listaprzetargow.pl/oferty/534818-licytacja-komornicza-mieszkanie-bytom-slaskie",
        pierwsze_wykrycie=DZIS,
        miasto="Bytom",
        dzielnica="Ruda",
        cena_wywolawcza=194100,
        metraz=121.6,
        pokoje=4,
        pietro="4",
        data_licytacji="2026-10-13",
        media={"woda": True, "prad": True, "gaz": None},
        flaga_budynek={"poziom": "brak", "powod": "Poza wzmianką o częściowym remoncie kuchni brak informacji o budynku."},
        flaga_okolica={"poziom": "brak", "powod": "Ogłoszenie nie podaje ulicy, więc okolicy nie da się sprawdzić."},
        perelka=True,
        niekompletna=True,
        notatka="1596 zł/m²; powyżej progu o 14 100 zł; duży metraż; brak ulicy w ogłoszeniu",
        opis="Przestronne mieszkanie o powierzchni 121,60 m² na czwartym piętrze budynku wielorodzinnego: cztery pokoje, kuchnia w otwartej przestrzeni z przedpokojem, dwie łazienki, balkon. Lokal po częściowym remoncie (m.in. kuchnia), z instalacjami wodno-kanalizacyjną i elektryczną.",
    ),
    Oferta(
        id="seed-katowice-49m",
        zrodlo="listaprzetargow.pl",
        link="https://listaprzetargow.pl/oferty/537646-licytacja-komornicza-mieszkanie-katowice-slaskie",
        pierwsze_wykrycie=DZIS,
        miasto="Katowice",
        cena_wywolawcza=131315,
        metraz=49.5,
        pokoje=2,
        pietro="11",
        data_licytacji="2026-09-24",
        wadium=17509,
        stan_prawny_uwagi="Adres i kontakt ukryte za płatnym dostępem portalu — nie udało się ustalić ulicy ani dzielnicy.",
        flaga_budynek={"poziom": "brak", "powod": "Wieżowiec z lat 80., brak dalszych szczegółów."},
        flaga_okolica={"poziom": "brak", "powod": "Ogłoszenie nie podaje ulicy, więc okolicy nie da się sprawdzić."},
        niekompletna=True,
        notatka="2653 zł/m²; bardzo dobra cena w Katowicach; brak ulicy w ogłoszeniu",
        opis="Mieszkanie o powierzchni 49,5 m² w Katowicach, na wysokim piętrze w wieżowcu z lat 80. Dwa pokoje, kuchnia, łazienka z WC oraz komórka wewnętrzna.",
    ),
    Oferta(
        id="seed-bytom-66m",
        zrodlo="listaprzetargow.pl",
        link="https://listaprzetargow.pl/oferty/530130-licytacja-komornicza-mieszkanie-bytom-slaskie",
        pierwsze_wykrycie=DZIS,
        miasto="Bytom",
        cena_wywolawcza=132750,
        metraz=65.93,
        pokoje=2,
        pietro="1",
        data_licytacji="2026-09-15",
        stan_prawny_uwagi="Udział 4/100 w nieruchomości wspólnej to standardowy zapis odrębnej własności lokalu, nie ułamek samego mieszkania.",
        flaga_budynek={"poziom": "brak", "powod": "Brak opisu stanu budynku w ogłoszeniu."},
        flaga_okolica={"poziom": "brak", "powod": "Ogłoszenie nie podaje ulicy, więc okolicy nie da się sprawdzić."},
        niekompletna=True,
        notatka="2013 zł/m²; duży metraż; brak ulicy w ogłoszeniu",
        opis="Lokal mieszkalny stanowiący odrębną nieruchomość w Bytomiu z udziałem 4/100 w nieruchomości wspólnej (grunt i części wspólne budynku). Cena wywołania 132 750 zł przy sumie oszacowania 177 000 zł.",
    ),
    Oferta(
        id="seed-bytom-36m",
        zrodlo="listaprzetargow.pl",
        link="https://listaprzetargow.pl/oferty/531356-licytacja-komornicza-mieszkanie-bytom-slaskie",
        pierwsze_wykrycie=DZIS,
        miasto="Bytom",
        cena_wywolawcza=124500,
        metraz=36.29,
        pokoje=2,
        pietro="3",
        data_licytacji="2026-09-22",
        flaga_budynek={"poziom": "zielona", "powod": "Budynek opisany jako zadbany, dobry stan techniczny."},
        flaga_okolica={"poziom": "brak", "powod": "Ogłoszenie nie podaje ulicy, więc okolicy nie da się sprawdzić."},
        niekompletna=True,
        notatka="3431 zł/m²; zadbany budynek z lat 80.; brak ulicy w ogłoszeniu",
        opis="Dwupokojowe mieszkanie o powierzchni ok. 40 m² z balkonem i piwnicą, w zadbanym czteropiętrowym budynku z lat 80., na trzecim piętrze. Lokal w dobrym stanie technicznym, z kuchnią i łazienką.",
    ),
    Oferta(
        id="seed-zabrze-34m",
        zrodlo="listaprzetargow.pl",
        link="https://listaprzetargow.pl/oferty/522975-licytacja-komornicza-mieszkanie-zabrze-slaskie",
        pierwsze_wykrycie=DZIS,
        miasto="Zabrze",
        cena_wywolawcza=108338,
        metraz=34.45,
        pokoje=1,
        pietro="6",
        data_licytacji="2026-10-27",
        flaga_budynek={"poziom": "brak", "powod": "Blok z 1967 r., brak opisu stanu technicznego budynku."},
        flaga_okolica={"poziom": "brak", "powod": "Ogłoszenie nie podaje ulicy, więc okolicy nie da się sprawdzić."},
        niekompletna=True,
        notatka="3145 zł/m²; stan do remontu to atut cenowy przy remoncie od zera; brak ulicy w ogłoszeniu",
        opis="Lokal mieszkalny o powierzchni ok. 34,5 m² na 6. piętrze bloku z 1967 roku: pokój, ślepa kuchnia, przedpokój, łazienka z WC, balkon. Mieszkanie stanowiące pełną własność jest w stanie do remontu.",
    ),
    Oferta(
        id="seed-zabrze-kamienica",
        zrodlo="listaprzetargow.pl",
        link="https://listaprzetargow.pl/oferty/535669-licytacja-komornicza-mieszkanie-zabrze-slaskie",
        pierwsze_wykrycie=DZIS,
        miasto="Zabrze",
        cena_wywolawcza=106024,
        metraz=36.3,
        pokoje=1,
        pietro="1",
        data_licytacji="2026-09-21",
        media={"woda": True, "prad": True, "gaz": None},
        flaga_budynek={"poziom": "brak", "powod": "Kamienica, brak opisu stanu technicznego."},
        flaga_okolica={"poziom": "brak", "powod": "Ogłoszenie nie podaje ulicy, więc okolicy nie da się sprawdzić."},
        niekompletna=True,
        notatka="2921 zł/m²; kamienica wymaga oględzin; brak ulicy w ogłoszeniu",
        opis="Kawalerka o powierzchni ok. 36 m² na pierwszym piętrze kamienicy: pokój, kuchnia, łazienka z WC, przedpokój, przynależna piwnica. Lokal z mediami: woda, kanalizacja, siła.",
    ),
    Oferta(
        id="seed-chorzow-kawalerka",
        zrodlo="listaprzetargow.pl",
        link="https://listaprzetargow.pl/oferty/537008-licytacja-komornicza-mieszkanie-chorzow-slaskie",
        pierwsze_wykrycie=DZIS,
        miasto="Chorzów",
        cena_wywolawcza=59250,
        metraz=23.21,
        pokoje=1,
        pietro="parter",
        data_licytacji="2026-10-19",
        stan_prawny_uwagi="Ogłoszenie wprost wskazuje konieczność formalnej legalizacji wydzielonej łazienki i weryfikacji wentylacji.",
        flaga_budynek={"poziom": "zolta", "powod": "wymagana legalizacja zmian w lokalu"},
        flaga_okolica={"poziom": "brak", "powod": "Ogłoszenie nie podaje ulicy, więc okolicy nie da się sprawdzić."},
        niekompletna=True,
        notatka="2553 zł/m²; najniższy próg wejścia w puli; do sprawdzenia: legalizacja łazienki",
        opis="Kawalerka o powierzchni 23,21 m² z piwnicą, na parterze: pokój, kuchnia, wydzielona łazienka. Konieczna formalna legalizacja wydzielonej łazienki i weryfikacja wentylacji.",
    ),
]

for o in oferty:
    if o.perelka is False and o.cena_wywolawcza and o.cena_wywolawcza > PROG_PODSTAWOWY:
        raise SystemExit(f"Oferta {o.id} przekracza próg, a nie jest oznaczona jako perełka")

oferty.sort(key=klucz_sortowania)

dane = {
    "wygenerowano": f"{DZIS}T09:00:00+00:00",
    "prog_podstawowy": PROG_PODSTAWOWY,
    "prog_perelki": PROG_PERELKI,
    "odrzucone_filtrem": 0,
    "zrodla": [
        {"nazwa": "przetargi.adradar.pl", "ok": True, "liczba": 1,
         "uwaga": "Filtr 'mieszkania' przekierowuje na wyniki archiwalne, więc użyto listy niefiltrowanej i odsiano typ ręcznie."},
        {"nazwa": "listaprzetargow.pl", "ok": True, "liczba": 7,
         "uwaga": "Sprawdzono Katowice, Sosnowiec, Bytom, Gliwice, Zabrze i Chorzów. Ulice ukryte za płatnym dostępem portalu."},
        {"nazwa": "licytacje.komornik.pl", "ok": False, "liczba": 0,
         "uwaga": "Nie sprawdzone w tym przebiegu — służy do ręcznej weryfikacji terminu i stanu prawnego."},
        {"nazwa": "syndykaukcje.pl", "ok": False, "liczba": 0, "uwaga": "Nie sprawdzone w tym przebiegu."},
        {"nazwa": "Pozostałe miasta", "ok": False, "liczba": 0,
         "uwaga": "Nie odpytano osobno: Świętochłowice, Siemianowice, Mysłowice, Dąbrowa Górnicza, Tychy, Będzin, Piekary, Czeladź, Ruda Śląska."},
    ],
    "oferty": [{**asdict(o), "cena_za_m2": o.cena_za_m2} for o in oferty],
}

DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
DATA_FILE.write_text(json.dumps(dane, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"Zapisano {len(oferty)} ofert startowych do {DATA_FILE}")

#!/usr/bin/env python3
"""
Zbieracz ofert mieszkań z licytacji komorniczych, aukcji syndyka i przetargów
w aglomeracji śląskiej. Wynik zapisuje do docs/data.json, który czyta strona.

Zasada nadrzędna (za skillem ZF Nieruchomości):
    Twardo odrzucaj tylko to, co ogłoszenie mówi WPROST. Resztę oznaczaj flagą.
    Nigdy nie zgaduj i nie uzupełniaj pól wartościami domyślnymi.

Uruchomienie lokalne:
    pip install -r scraper/requirements.txt
    python scraper/scrape.py
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
import hashlib
import logging
import datetime as dt
from dataclasses import dataclass, field, asdict
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Konfiguracja
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = ROOT / "docs" / "data.json"

PROG_PODSTAWOWY = 180_000     # zwykły limit ceny wywoławczej
PROG_PERELKI = 220_000        # limit dla ofert wyraźnie ponadprzeciętnych

# Ile dni trzymać ofertę po terminie licytacji, zanim zniknie z listy.
DNI_KARENCJI_PO_TERMINIE = 3

# Miasta w zasięgu. Klucz = slug listaprzetargow.pl, wartość = nazwa wyświetlana.
MIASTA = {
    "katowice": "Katowice",
    "sosnowiec": "Sosnowiec",
    "chorzow": "Chorzów",
    "bytom": "Bytom",
    "zabrze": "Zabrze",
    "gliwice": "Gliwice",
    "ruda-slaska": "Ruda Śląska",
    "swietochlowice": "Świętochłowice",
    "siemianowice-slaskie": "Siemianowice Śląskie",
    "myslowice": "Mysłowice",
    "dabrowa-gornicza": "Dąbrowa Górnicza",
    "tychy": "Tychy",
    "bedzin": "Będzin",
    "piekary-slaskie": "Piekary Śląskie",
    "czeladz": "Czeladź",
}

# Nazwy miast do rozpoznawania w tekście z Adradara (bez slugów).
NAZWY_MIAST = set(MIASTA.values())

KATEGORIE_LP = {
    "licytacje-komornicze": "licytacja komornicza",
    "przetargi": "przetarg",
    "syndyk": "syndyk",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "pl-PL,pl;q=0.9",
}

PAUZA = 1.5          # sekundy między żądaniami — nie młotkujemy serwisów
TIMEOUT = 25
PROBY = 3

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("przetargi")


# ---------------------------------------------------------------------------
# Reguły filtrowania — dokładnie za references/kryteria.md
# ---------------------------------------------------------------------------

# Ogrzewanie węglowe. UWAGA: samo "piec"/"ogrzewanie piecowe" NIE odrzuca —
# piec bywa gazowy i takie mieszkania są akceptowalne.
FRAZY_WEGIEL = [
    r"piec\s+w[ęe]glow",
    r"ogrzewanie\s+w[ęe]glow",
    r"opalan\w*\s+w[ęe]glem",
    r"na\s+w[ęe]giel",
    r"kot[łl]ownia\s+w[ęe]glowa",
    r"piec\s+kaflowy\s+na\s+w[ęe]giel",
]

# Stan wykluczający remont. Dotyczy BUDYNKU, nie mieszkania —
# "zdewastowany lokal" czy "do kapitalnego remontu" to NIE przesłanki odrzucenia.
FRAZY_STAN_WYKLUCZAJACY = [
    r"do\s+rozbi[óo]rki",
    r"nakaz\s+rozbi[óo]rki",
    r"grozi\s+zawaleniem",
    r"katastrofa\s+budowlana",
    r"budynek\s+wy[łl][ąa]czony\s+z\s+u[żz]ytkowania",
    r"zakaz\s+u[żz]ytkowania",
]

# Brak PRZYŁĄCZA wody lub prądu. "Odcięte media", "instalacje do wymiany",
# "brak instalacji wewnętrznych" to nie to samo — odcięcie za długi jest odwracalne.
FRAZY_BRAK_MEDIOW = [
    r"brak\s+przy[łl][ąa]cza\s+wod",
    r"brak\s+przy[łl][ąa]cza\s+(?:energii|elektr|pr[ąa]du)",
    r"nieruchomo[śs][ćc]\s+bez\s+przy[łl][ąa]czy",
    r"brak\s+dost[ęe]pu\s+do\s+wody\s+i\s+pr[ąa]du",
]

# Udział ułamkowy w SAMYM LOKALU (nie w częściach wspólnych).
# To odrzucenie jest ważne, bo takie pozycje wyglądają jak rewelacyjne okazje
# cenowe: udział 1/6 w mieszkaniu wartym 107 tys. wychodzi 13 tys. i trafia
# na szczyt sortowania po cenie, a kupujesz współwłasność, nie mieszkanie.
#
# KLUCZOWE ROZRÓŻNIENIE: prawie każde obwieszczenie zawiera zwrot
# "wraz z udziałem 327/10000 w częściach wspólnych" — to normalne i pożądane,
# tak wygląda każda odrębna własność lokalu. Stąd negatywny lookahead poniżej.
_NIE_WSPOLNE = r"(?!cz[ęe][śs]ci|nieruchomo[śs]ci\s+wsp|prawie\s+w[łl]asno[śs]ci\s+nieruchomo[śs]ci\s+wsp)"
_CEL_LOKAL = (
    r"(?:(?:samodzielnym|prawie|prawa)\s+)*"
    r"(?:w[łl]asno[śs]ci\s+)?(?:sp[óo][łl]dzielcz\w+\s+)?(?:w[łl]asno[śs]ciow\w+\s+)?"
    r"(?:praw\w*\s+do\s+)?(?:lokal\w*|mieszkani\w*)"
)

FRAZY_UDZIAL_W_LOKALU = [
    # "udział 1/2 w mieszkaniu", "udziałem wynoszącym 1/3 w prawie własności lokalu"
    rf"udzia[łl]\w*\s+(?:wynosz[ąa]c\w+\s+)?\d+\s*/\s*\d+\s+w\s+{_NIE_WSPOLNE}\s*{_CEL_LOKAL}",
    # odwrotna kolejność: "1/6 udziału w samodzielnym mieszkaniu"
    rf"\d+\s*/\s*\d+\s+udzia[łl]\w*\s+w\s+{_NIE_WSPOLNE}\s*{_CEL_LOKAL}",
    # "UDZIAŁ 1/6 W SPÓŁDZIELCZYM WŁASNOŚCIOWYM PRAWIE DO LOKALU"
    r"udzia[łl]\w*\s+\d+\s*/\s*\d+\s+w\s+(?:sp[óo][łl]dzielcz\w+\s+)?"
    r"(?:w[łl]asno[śs]ciow\w+\s+)?praw\w*\s+do\s+lokalu",
]

# Frazy sygnalizujące, że przedmiotem NIE jest mieszkanie.
FRAZY_NIE_MIESZKANIE = [
    r"lokal\s+u[żz]ytkowy",
    r"pe[łl]ni[ąa]c\w*\s+funkcj[ęe]\s+baru",
    r"bar\s*-\s*restauracj",
    r"gara[żz]\s+wielostanowiskowy",
    r"nieruchomo[śs][ćc]\s+gruntowa\b",
]

# Sygnały do żółtej flagi budynku — wymagają sprawdzenia na miejscu.
SYGNALY_ZOLTE = [
    (r"zawilgoc", "wzmianka o zawilgoceniu"),
    (r"zagrzybi", "wzmianka o zagrzybieniu"),
    (r"pustostan", "lokal opisany jako pustostan"),
    (r"rewitalizacj", "budynek przeznaczony do rewitalizacji"),
    (r"nieociepl", "budynek nieocieplony"),
    (r"z\s+(?:XIX|XVIII)\s+wieku", "bardzo stara zabudowa"),
    (r"z\s+ok\.?\s+1[89]\d\d\s+rok", "bardzo stara zabudowa"),
    (r"legalizacj", "wymagana legalizacja zmian w lokalu"),
    (r"nadzoru\s+budowlanego", "postępowanie nadzoru budowlanego"),
    (r"s[łl]u[żz]ebno[śs][ćc]", "obciążenie służebnością"),
    (r"stan\s+techniczny\w*\s+pogorszon", "pogorszony stan techniczny"),
]

# Sygnały do czerwonej flagi budynku.
SYGNALY_CZERWONE = [
    (r"po\s+po[żz]arze", "skutki pożaru"),
    (r"remontu\s+po\s+po[żz]arze", "skutki pożaru"),
    (r"po\s+zalaniu", "skutki zalania"),
    (r"stan\w*\s+awaryjn", "stan awaryjny"),
    (r"dezynfekcj", "wymagana dezynfekcja lokalu"),
]

# Sygnały pozytywne — pozwalają dać zieloną flagę budynku.
SYGNALY_ZIELONE = [
    (r"zadban\w+.{0,40}budyn", "budynek opisany jako zadbany"),
    (r"budynek\w*\s+ociepl", "budynek ocieplony"),
    (r"dobry\w*\s+stan\w*\s+techniczn", "dobry stan techniczny"),
    (r"po\s+termomodernizacj", "po termomodernizacji"),
]

# Frazy potwierdzające media (do informacji, nie do odrzucania).
MEDIA_WZORCE = {
    "woda": [r"\bwod(?:a|no|oci[ąa]g)", r"instalacj\w*\s+wodn"],
    "prad": [r"\belektryczn", r"\bpr[ąa]d\b", r"\bsi[łl]a\b", r"energetyczn"],
    "gaz": [r"\bgaz(?:owa|owe|owy|u|em)?\b"],
}


def dopasuj(wzorce: list[str], tekst: str) -> str | None:
    """Zwraca pierwszy dopasowany wzorzec albo None."""
    for w in wzorce:
        if re.search(w, tekst, re.IGNORECASE):
            return w
    return None


# ---------------------------------------------------------------------------
# Model oferty
# ---------------------------------------------------------------------------


@dataclass
class Oferta:
    id: str
    zrodlo: str
    zrodla_dodatkowe: list[str] = field(default_factory=list)
    link: str = ""
    pierwsze_wykrycie: str = ""

    adres: str | None = None
    miasto: str | None = None
    dzielnica: str | None = None
    cena_wywolawcza: int | None = None
    metraz: float | None = None
    pokoje: int | None = None
    pietro: str | None = None
    data_licytacji: str | None = None
    wadium: int | None = None
    typ_postepowania: str = "licytacja komornicza"
    stan_prawny_uwagi: str | None = None

    ogrzewanie: str | None = None
    media: dict = field(default_factory=lambda: {"woda": None, "prad": None, "gaz": None})
    flaga_budynek: dict = field(default_factory=lambda: {"poziom": "brak", "powod": ""})
    flaga_okolica: dict = field(default_factory=lambda: {"poziom": "brak", "powod": ""})
    perelka: bool = False
    notatka: str = ""
    niekompletna: bool = False
    opis: str = ""

    @property
    def cena_za_m2(self) -> int | None:
        if not self.cena_wywolawcza or not self.metraz:
            return None
        return round(self.cena_wywolawcza / self.metraz)


# ---------------------------------------------------------------------------
# Warstwa HTTP
# ---------------------------------------------------------------------------


class Pobieracz:
    def __init__(self) -> None:
        self.sesja = requests.Session()
        self.sesja.headers.update(HEADERS)
        self.licznik = 0

    def get(self, url: str) -> str | None:
        for proba in range(1, PROBY + 1):
            try:
                time.sleep(PAUZA)
                self.licznik += 1
                r = self.sesja.get(url, timeout=TIMEOUT)
                if r.status_code == 200:
                    return r.text
                if r.status_code in (403, 429):
                    log.warning("%s → HTTP %s (próba %s)", url, r.status_code, proba)
                    time.sleep(PAUZA * 4 * proba)
                    continue
                if 400 <= r.status_code < 500:
                    log.warning("%s → HTTP %s, pomijam", url, r.status_code)
                    return None
                log.warning("%s → HTTP %s (próba %s)", url, r.status_code, proba)
            except requests.RequestException as e:
                log.warning("%s → %s (próba %s)", url, type(e).__name__, proba)
            time.sleep(PAUZA * 2 * proba)
        return None


def tekst(html: str) -> str:
    """Płaski tekst strony z separatorami, do regexów."""
    zupa = BeautifulSoup(html, "html.parser")
    for tag in zupa(["script", "style", "noscript"]):
        tag.decompose()
    return re.sub(r"[ \t\xa0]+", " ", zupa.get_text(" ", strip=True))


# ---------------------------------------------------------------------------
# Parsery pomocnicze
# ---------------------------------------------------------------------------


def liczba_pln(s: str) -> int | None:
    """'131 315 zł' / '131 314,50 zł' → 131315"""
    s = s.replace("\xa0", " ")
    m = re.search(r"(\d[\d  ]*(?:,\d+)?)\s*z[łl]", s, re.IGNORECASE)
    if not m:
        return None
    surowa = m.group(1).replace(" ", "").replace(" ", "").replace(",", ".")
    try:
        # math.floor(x + 0.5), bo round() w Pythonie zaokrągla połówki
        # do liczby parzystej: round(131314.5) daje 131314, nie 131315.
        return int(float(surowa) + 0.5)
    except ValueError:
        return None


def metraz_z(s: str) -> float | None:
    """'49,50 m2' → 49.5. Ignoruje wartości absurdalne dla mieszkania."""
    s = s.replace("\xa0", " ")
    for m in re.finditer(r"(\d{1,4}(?:[,.]\d+)?)\s*m\s*(?:2|²)", s, re.IGNORECASE):
        try:
            v = float(m.group(1).replace(",", "."))
        except ValueError:
            continue
        if 12 <= v <= 400:      # poza tym zakresem to nie mieszkanie albo błąd portalu
            return v
    return None


def data_iso(s: str) -> str | None:
    """'24-09-2026' lub '2026-09-24' → '2026-09-24'"""
    m = re.search(r"\b(\d{2})-(\d{2})-(\d{4})\b", s)
    if m:
        return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
    m = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", s)
    if m:
        return m.group(0)
    return None


def zrob_id(*czesci) -> str:
    surowe = "|".join(str(c or "").strip().lower() for c in czesci)
    return hashlib.sha1(surowe.encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Źródło 1: listaprzetargow.pl
# ---------------------------------------------------------------------------

RE_LINK_LP = re.compile(
    r"/oferty/(\d+)-(licytacja-komornicza|przetarg|syndyk)-mieszkanie-", re.IGNORECASE
)


def zbierz_listaprzetargow(pob: Pobieracz) -> tuple[list[Oferta], dict]:
    """
    Lista ofert per miasto i kategoria, potem strona szczegółów każdej nowej oferty.
    Portal ukrywa dokładny adres bez konta premium — to znane ograniczenie,
    raportujemy je jawnie zamiast udawać, że adres jest nieznany z innego powodu.
    """
    znalezione: dict[str, Oferta] = {}
    linki: dict[str, str] = {}     # id_oferty -> url szczegółów
    bledy = 0
    strony_ok = 0

    for slug, miasto in MIASTA.items():
        for kat_slug, typ in KATEGORIE_LP.items():
            url = f"https://listaprzetargow.pl/oferty/{kat_slug}/mieszkania/{slug}"
            html = pob.get(url)
            if not html:
                bledy += 1
                continue
            strony_ok += 1
            zupa = BeautifulSoup(html, "html.parser")

            for a in zupa.find_all("a", href=True):
                m = RE_LINK_LP.search(a["href"])
                if not m:
                    continue
                nr = m.group(1)
                # Pomijamy zakończone — portal oznacza je w treści bloku.
                blok = a
                for _ in range(3):
                    if blok.parent is not None:
                        blok = blok.parent
                blok_txt = blok.get_text(" ", strip=True)
                if re.search(r"\bZako[ńn]czona\b", blok_txt, re.IGNORECASE):
                    continue
                pelny = a["href"]
                if pelny.startswith("/"):
                    pelny = "https://listaprzetargow.pl" + pelny
                linki[nr] = pelny

    log.info("listaprzetargow: %s stron OK, %s błędów, %s ofert do pobrania",
             strony_ok, bledy, len(linki))

    for nr, url in linki.items():
        html = pob.get(url)
        if not html:
            bledy += 1
            continue
        o = parsuj_szczegoly_lp(html, url, nr)
        if o:
            znalezione[o.id] = o

    raport = {
        "nazwa": "listaprzetargow.pl",
        "ok": strony_ok > 0,
        "liczba": len(znalezione),
        "uwaga": (
            "Dokładna ulica i kontakt są ukryte za płatnym dostępem portalu — "
            "widoczne jest tylko miasto, czasem dzielnica."
            if znalezione else
            f"Nie udało się pobrać żadnej oferty ({bledy} błędów)."
        ),
    }
    return list(znalezione.values()), raport


def parsuj_szczegoly_lp(html: str, url: str, nr: str) -> Oferta | None:
    t = tekst(html)

    miasto = None
    m = re.search(r"Miasto\s+([A-ZŻŹĆĄŚĘŁÓŃ][\w\-ąćęłńóśźż ]{2,30}?)\s+Powierzchnia", t)
    if m:
        kand = m.group(1).strip()
        if kand in NAZWY_MIAST:
            miasto = kand
    if not miasto:
        for nazwa in NAZWY_MIAST:
            if re.search(rf"\b{re.escape(nazwa)}\b", t):
                miasto = nazwa
                break
    if not miasto:
        return None

    dzielnica = None
    m = re.search(rf"{re.escape(miasto)},\s*([A-ZŻŹĆĄŚĘŁÓŃ][\w\-ąćęłńóśźż ]{{2,25}}?)\s+Mieszkanie", t)
    if m and m.group(1).strip().lower() not in ("śląskie", "slaskie"):
        dzielnica = m.group(1).strip()

    cena = None
    m = re.search(r"Cena\s+([\d  ]+(?:,\d+)?)\s*z[łl]", t, re.IGNORECASE)
    if m:
        cena = liczba_pln(m.group(0))

    metraz = None
    m = re.search(r"Powierzchnia\s+([\d]+(?:,\d+)?)\s*m\s*2", t, re.IGNORECASE)
    if m:
        metraz = metraz_z(m.group(0))
    if metraz is None:
        metraz = metraz_z(t)

    pokoje = None
    m = re.search(r"Liczba\s+pokoi\s+(\d{1,2})", t, re.IGNORECASE)
    if m:
        pokoje = int(m.group(1))

    pietro = None
    m = re.search(r"Pi[ęe]tro\s+(parter|\d{1,2}|-)", t, re.IGNORECASE)
    if m and m.group(1) != "-":
        pietro = m.group(1)

    wadium = None
    m = re.search(r"Wadium\s+([\d  ]+(?:,\d+)?)\s*z[łl]", t, re.IGNORECASE)
    if m:
        wadium = liczba_pln(m.group(0))

    termin = None
    m = re.search(r"Termin\s+wp[łl]aty\s+wadium\s+(\d{2}-\d{2}-\d{4})", t, re.IGNORECASE)
    if m:
        termin = data_iso(m.group(1))

    typ = "licytacja komornicza"
    if re.search(r"Tryb\s+sprzeda[żz]y\s+Przetarg", t, re.IGNORECASE):
        typ = "przetarg"
    elif re.search(r"Tryb\s+sprzeda[żz]y\s+.{0,20}syndyk", t, re.IGNORECASE):
        typ = "syndyk"

    opis = ""
    m = re.search(r"Opis\s+(.{40,1200}?)(?:Odblokuj|Historyczne\s+ceny|Podobne\s+oferty)", t, re.DOTALL)
    if m:
        opis = re.sub(r"\s+", " ", m.group(1)).strip()

    ulica = None
    m = re.search(r"Ulica\s+((?!Poka[żz])[\w\.\-ąćęłńóśźż ]{3,40}?)\s+Liczba", t)
    if m:
        ulica = m.group(1).strip()

    return Oferta(
        id=zrob_id("lp", nr),
        zrodlo="listaprzetargow.pl",
        link=url,
        adres=ulica,
        miasto=miasto,
        dzielnica=dzielnica,
        cena_wywolawcza=cena,
        metraz=metraz,
        pokoje=pokoje,
        pietro=pietro,
        data_licytacji=termin,
        wadium=wadium,
        typ_postepowania=typ,
        opis=opis,
    )


# ---------------------------------------------------------------------------
# Źródło 2: przetargi.adradar.pl
# ---------------------------------------------------------------------------

# Filtr /p/mieszkania/... przekierowuje na wyniki ARCHIWALNE mimo jawnego
# ?page=1, dlatego korzystamy z listy niefiltrowanej i odsiewamy typ sami.
ADRADAR_LISTY = [
    "https://przetargi.adradar.pl/p/a/74442/%C5%9Bl%C4%85skie/licytacje_komornicze",
    "https://przetargi.adradar.pl/p/a/74442/%C5%9Bl%C4%85skie/zakup_od_syndyka",
    "https://przetargi.adradar.pl/p/a/74442/%C5%9Bl%C4%85skie/spoldzielnia_mieszkaniowa",
]

RE_LINK_ADRADAR = re.compile(r"/przetarg/mieszkania/[^/]+/([a-z_]+)/(\d+)", re.IGNORECASE)

TYP_ADRADAR = {
    "licytacje_komornicze": "licytacja komornicza",
    "zakup_od_syndyka": "syndyk",
    "spoldzielnia_mieszkaniowa": "przetarg spółdzielni",
}


def zbierz_adradar(pob: Pobieracz, strony: int = 4) -> tuple[list[Oferta], dict]:
    znalezione: dict[str, Oferta] = {}
    strony_ok = 0
    bledy = 0

    for baza in ADRADAR_LISTY:
        for nr_strony in range(1, strony + 1):
            url = f"{baza}?page={nr_strony}"
            html = pob.get(url)
            if not html:
                bledy += 1
                continue

            zupa = BeautifulSoup(html, "html.parser")
            t_strony = zupa.get_text(" ", strip=True)
            if re.search(r"ARCHIWALNE", t_strony) and nr_strony == 1:
                log.warning("Adradar %s → strona zwróciła wyniki archiwalne", url)

            trafienia = 0
            for a in zupa.find_all("a", href=True):
                m = RE_LINK_ADRADAR.search(a["href"])
                if not m:
                    continue
                kategoria, nr = m.group(1), m.group(2)
                blok = a
                for _ in range(4):
                    if blok.parent is not None:
                        blok = blok.parent
                blok_txt = re.sub(r"\s+", " ", blok.get_text(" ", strip=True))
                if re.search(r"\bARCHIWALNE\b", blok_txt):
                    continue

                o = parsuj_adradar(blok_txt, a, kategoria, nr)
                if o and o.id not in znalezione:
                    znalezione[o.id] = o
                    trafienia += 1

            strony_ok += 1
            if trafienia == 0 and nr_strony > 1:
                break     # dalsze strony nic już nie dają

    raport = {
        "nazwa": "przetargi.adradar.pl",
        "ok": strony_ok > 0 and len(znalezione) > 0,
        "liczba": len(znalezione),
        "uwaga": (
            "Lista niefiltrowana (filtr 'mieszkania' przekierowuje na archiwum) — "
            "typ nieruchomości odsiewany po stronie skryptu. Bez płatnego dostępu "
            "portal pokazuje tylko część aktualnych ogłoszeń."
            if znalezione else
            f"Brak ofert z tego źródła ({bledy} błędów pobrania)."
        ),
    }
    return list(znalezione.values()), raport


def parsuj_adradar(blok: str, a, kategoria: str, nr: str) -> Oferta | None:
    if not re.search(r"Licytacja\s+komornicza\s+mieszkania|mieszkania", blok, re.IGNORECASE):
        return None

    miasto = None
    for nazwa in NAZWY_MIAST:
        if re.search(rf"\b{re.escape(nazwa)}\b", blok):
            miasto = nazwa
            break
    if not miasto:
        return None

    # Tytuł Adradara: "Licytacja komornicza mieszkania [Dzielnica, Miasto, Ulica]"
    dzielnica = None
    adres = None
    m = re.search(
        rf"mieszkania\s+([\w\-ąćęłńóśźżĄĆĘŁŃÓŚŹŻ\. ]{{2,40}}?),?\s*{re.escape(miasto)}"
        rf"(?:,\s*([\w\-ąćęłńóśźżĄĆĘŁŃÓŚŹŻ\.’' ]{{2,50}}?))?\s*(?:\.\.\.|Cena|Szczeg)",
        blok,
    )
    if m:
        kand_dz = (m.group(1) or "").strip(" ,.")
        kand_ul = (m.group(2) or "").strip(" ,.")
        if kand_dz and kand_dz != miasto and len(kand_dz) < 30:
            dzielnica = kand_dz
        if kand_ul and len(kand_ul) < 45:
            adres = kand_ul
    if not adres:
        m = re.search(rf"{re.escape(miasto)},\s*(?:ul\.\s*)?([A-ZŻŹĆĄŚĘŁÓŃ][\w\-ąćęłńóśźż\.’' ]{{2,45}}?)\s*(?:\.\.\.|Cena)", blok)
        if m:
            adres = m.group(1).strip(" ,.")

    cena = None
    m = re.search(r"Cena\s+wywo[łl]awcza:?\s*([\d  ]+(?:,\d+)?)\s*z[łl]", blok, re.IGNORECASE)
    if m:
        cena = liczba_pln(m.group(0))

    metraz = None
    m = re.search(r"(\d{1,3}(?:[,.]\d+)?)\s*m[²2]\s+\d+\s+pok", blok)
    if m:
        metraz = metraz_z(m.group(0))
    if metraz is None:
        # cena za m² pozwala odtworzyć metraż, gdy portal go nie wypisał osobno
        m2 = re.search(r"([\d  ]+(?:,\d+)?)\s*z[łl]\s*/\s*m[²2]", blok, re.IGNORECASE)
        za_m2 = liczba_pln(m2.group(0).replace("/m²", "").replace("/m2", "")) if m2 else None
        if cena and za_m2 and za_m2 > 0:
            szac = cena / za_m2
            if 12 <= szac <= 400:
                metraz = round(szac, 1)

    pokoje = None
    m = re.search(r"(\d{1,2})\s+pok", blok)
    if m:
        pokoje = int(m.group(1))

    termin = None
    m = re.search(r"Termin:?\s*(\d{4}-\d{2}-\d{2})", blok)
    if m:
        termin = m.group(1)

    href = a["href"]
    if href.startswith("/"):
        href = "https://przetargi.adradar.pl" + href

    opis = ""
    m = re.search(r"\.\.\.(.{40,1200}?)(?:Szczeg[óo][łl]y|Cena\s+wywo)", blok, re.DOTALL)
    if m:
        opis = re.sub(r"\s+", " ", m.group(1)).strip()

    return Oferta(
        id=zrob_id("adradar", nr),
        zrodlo="przetargi.adradar.pl",
        link=href,
        adres=adres,
        miasto=miasto,
        dzielnica=dzielnica,
        cena_wywolawcza=cena,
        metraz=metraz,
        pokoje=pokoje,
        data_licytacji=termin,
        typ_postepowania=TYP_ADRADAR.get(kategoria, "licytacja komornicza"),
        opis=opis,
    )


# ---------------------------------------------------------------------------
# Filtrowanie twarde
# ---------------------------------------------------------------------------


def odrzucic(o: Oferta) -> str | None:
    """Zwraca powód odrzucenia albo None. Odrzucamy tylko to, co napisane WPROST."""
    t = " ".join(filter(None, [o.opis, o.adres or "", o.dzielnica or ""]))

    if o.miasto not in NAZWY_MIAST:
        return f"miasto poza zasięgiem ({o.miasto})"

    if o.cena_wywolawcza is not None and o.cena_wywolawcza > PROG_PERELKI:
        return f"cena {o.cena_wywolawcza} zł powyżej progu perełki"

    if dopasuj(FRAZY_UDZIAL_W_LOKALU, t):
        return "przedmiotem jest udział ułamkowy w samym lokalu, nie cały lokal"

    if dopasuj(FRAZY_WEGIEL, t):
        return "ogrzewanie węglowe wskazane wprost"

    if dopasuj(FRAZY_STAN_WYKLUCZAJACY, t):
        return "budynek wykluczony z użytkowania / do rozbiórki"

    if dopasuj(FRAZY_BRAK_MEDIOW, t):
        return "brak przyłącza wody lub prądu wskazany wprost"

    if dopasuj(FRAZY_NIE_MIESZKANIE, t):
        return "przedmiotem nie jest lokal mieszkalny"

    # Oferta powyżej progu podstawowego przechodzi tylko jako perełka.
    if o.cena_wywolawcza is not None and o.cena_wywolawcza > PROG_PODSTAWOWY:
        if not o.perelka:
            return f"cena {o.cena_wywolawcza} zł powyżej progu {PROG_PODSTAWOWY} zł, a oferta nie jest ponadprzeciętna"

    if o.data_licytacji:
        try:
            d = dt.date.fromisoformat(o.data_licytacji)
            if d < dt.date.today() - dt.timedelta(days=DNI_KARENCJI_PO_TERMINIE):
                return f"termin licytacji minął ({o.data_licytacji})"
        except ValueError:
            pass

    return None


# ---------------------------------------------------------------------------
# Wzbogacanie i ocena
# ---------------------------------------------------------------------------


def ustal_perelke(o: Oferta, mediana_m2: float | None) -> None:
    """
    Perełka = powyżej 180 tys., ale wyraźnie ponadprzeciętna.
    Sama cena mieszcząca się w progu 220 tys. NIE czyni oferty perełką.
    """
    if o.cena_wywolawcza is None or o.cena_wywolawcza <= PROG_PODSTAWOWY:
        o.perelka = False
        return
    if o.cena_wywolawcza > PROG_PERELKI:
        o.perelka = False
        return

    za_m2 = o.cena_za_m2
    if za_m2 is None or mediana_m2 is None:
        o.perelka = False
        return

    wyraznie_taniej = za_m2 <= mediana_m2 * 0.75
    duzy_metraz = (o.metraz or 0) >= 60
    o.perelka = bool(wyraznie_taniej and duzy_metraz)


def ustal_flagi(o: Oferta) -> None:
    t = o.opis or ""

    trafienie = None
    for wzor, powod in SYGNALY_CZERWONE:
        if re.search(wzor, t, re.IGNORECASE):
            trafienie = ("czerwona", powod)
            break
    if trafienie is None:
        for wzor, powod in SYGNALY_ZOLTE:
            if re.search(wzor, t, re.IGNORECASE):
                trafienie = ("zolta", powod)
                break
    if trafienie is None:
        for wzor, powod in SYGNALY_ZIELONE:
            if re.search(wzor, t, re.IGNORECASE):
                trafienie = ("zielona", powod)
                break

    if trafienie:
        o.flaga_budynek = {"poziom": trafienie[0], "powod": trafienie[1]}
    else:
        o.flaga_budynek = {
            "poziom": "brak",
            "powod": "Ogłoszenie nie zawiera informacji o stanie budynku.",
        }

    # Okolicy nie da się ocenić automatycznie bez API miejsc — i nie zgadujemy.
    if o.adres:
        o.flaga_okolica = {
            "poziom": "brak",
            "powod": "Adres znany — sprawdź okolicę na mapie (przycisk na karcie).",
        }
    else:
        o.flaga_okolica = {
            "poziom": "brak",
            "powod": "Ogłoszenie nie podaje ulicy, więc okolicy nie da się sprawdzić.",
        }

    # Ogrzewanie i media — tylko to, co w tekście.
    if re.search(
        r"ogrzewanie\s+miejskie|ogrzewaniem\s+miejskim"
        r"|c\.?\s?o\.?\b.{0,40}z\s+sieci|centralne\w*\s+ogrzewani\w+.{0,20}z\s+sieci"
        r"|z\s+sieci\s+miejskiej|ciep[łl]a\s+woda\s+z\s+sieci",
        t, re.IGNORECASE,
    ):
        o.ogrzewanie = "miejskie / z sieci"
    elif re.search(r"etażow\w+\s+gazow|piec\w*\s+gazow|kot[łl]\w*\s+gazow", t, re.IGNORECASE):
        o.ogrzewanie = "gazowe"
    elif re.search(r"ogrzewanie\s+elektryczn", t, re.IGNORECASE):
        o.ogrzewanie = "elektryczne"
    elif re.search(r"ogrzewanie\s+piecow|\bpiec\b", t, re.IGNORECASE):
        o.ogrzewanie = "piecowe — paliwo do sprawdzenia"
    else:
        o.ogrzewanie = None

    for klucz, wzorce in MEDIA_WZORCE.items():
        o.media[klucz] = True if dopasuj(wzorce, t) else None

    o.niekompletna = any(
        v is None for v in (o.cena_wywolawcza, o.metraz)
    ) or not o.adres

    o.notatka = zbuduj_notatke(o)


def zbuduj_notatke(o: Oferta) -> str:
    czesci = []
    za_m2 = o.cena_za_m2
    if za_m2:
        czesci.append(f"{za_m2} zł/m²")
    if o.perelka and o.cena_wywolawcza:
        nadwyzka = o.cena_wywolawcza - PROG_PODSTAWOWY
        czesci.append(f"powyżej progu o {nadwyzka:,} zł".replace(",", " "))
    if o.metraz and o.metraz >= 60:
        czesci.append("duży metraż")
    if o.flaga_budynek["poziom"] == "czerwona":
        czesci.append(f"ryzyko: {o.flaga_budynek['powod']}")
    elif o.flaga_budynek["poziom"] == "zolta":
        czesci.append(f"do sprawdzenia: {o.flaga_budynek['powod']}")
    if not o.adres:
        czesci.append("brak ulicy w ogłoszeniu")
    if o.ogrzewanie:
        czesci.append(f"ogrzewanie: {o.ogrzewanie}")
    return "; ".join(czesci) if czesci else "Brak danych do oceny poza ceną i metrażem."


# ---------------------------------------------------------------------------
# Deduplikacja
# ---------------------------------------------------------------------------


def klucz_dedup(o: Oferta) -> str:
    """Ta sama licytacja wychodzi z kilku źródeł — scalamy po cechach lokalu."""
    return "|".join([
        (o.miasto or "").lower(),
        str(int(o.metraz)) if o.metraz else "?",
        str(o.cena_wywolawcza or "?"),
        o.data_licytacji or "?",
    ])


PRIORYTET_ZRODLA = {"przetargi.adradar.pl": 0, "listaprzetargow.pl": 1}


def deduplikuj(oferty: list[Oferta]) -> list[Oferta]:
    grupy: dict[str, list[Oferta]] = {}
    for o in oferty:
        grupy.setdefault(klucz_dedup(o), []).append(o)

    wynik = []
    for grupa in grupy.values():
        if len(grupa) == 1:
            wynik.append(grupa[0])
            continue
        # Adradar wygrywa, bo podaje ulicę; resztą uzupełniamy puste pola.
        grupa.sort(key=lambda x: PRIORYTET_ZRODLA.get(x.zrodlo, 9))
        glowna, pozostale = grupa[0], grupa[1:]
        for inna in pozostale:
            for pole in ("adres", "dzielnica", "cena_wywolawcza", "metraz",
                         "pokoje", "pietro", "wadium", "data_licytacji"):
                if getattr(glowna, pole) is None:
                    setattr(glowna, pole, getattr(inna, pole))
            if len(inna.opis) > len(glowna.opis):
                glowna.opis = inna.opis
            if inna.zrodlo not in glowna.zrodla_dodatkowe:
                glowna.zrodla_dodatkowe.append(inna.zrodlo)
        wynik.append(glowna)
    return wynik


# ---------------------------------------------------------------------------
# Sortowanie domyślne
# ---------------------------------------------------------------------------

WAGA = {"zielona": 0, "zolta": 1, "brak": 1, "czerwona": 10}


def klucz_sortowania(o: Oferta):
    ocena = WAGA.get(o.flaga_budynek["poziom"], 1) + WAGA.get(o.flaga_okolica["poziom"], 1)
    za_m2 = o.cena_za_m2 or 10**9
    dni = 10**6
    if o.data_licytacji:
        try:
            dni = (dt.date.fromisoformat(o.data_licytacji) - dt.date.today()).days
        except ValueError:
            pass
    return (ocena, za_m2, dni)


# ---------------------------------------------------------------------------
# Zapis i merge stanu
# ---------------------------------------------------------------------------


def wczytaj_stan() -> dict:
    if DATA_FILE.exists():
        try:
            return json.loads(DATA_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            log.warning("data.json nieczytelny — startuję od zera")
    return {"oferty": [], "zrodla": [], "wygenerowano": None}


def zapisz(oferty: list[Oferta], raporty: list[dict], odrzucone: int) -> None:
    dane = {
        "wygenerowano": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "prog_podstawowy": PROG_PODSTAWOWY,
        "prog_perelki": PROG_PERELKI,
        "odrzucone_filtrem": odrzucone,
        "zrodla": raporty,
        "oferty": [
            {**asdict(o), "cena_za_m2": o.cena_za_m2}
            for o in oferty
        ],
    }
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(
        json.dumps(dane, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    log.info("Zapisano %s ofert do %s", len(oferty), DATA_FILE)


# ---------------------------------------------------------------------------
# Główny przebieg
# ---------------------------------------------------------------------------


def main() -> int:
    dzis = dt.date.today().isoformat()
    stan = wczytaj_stan()
    znane = {o["id"]: o for o in stan.get("oferty", [])}

    pob = Pobieracz()
    wszystkie: list[Oferta] = []
    raporty: list[dict] = []

    for funkcja, nazwa in ((zbierz_adradar, "Adradar"), (zbierz_listaprzetargow, "ListaPrzetargow")):
        try:
            oferty, raport = funkcja(pob)
            wszystkie.extend(oferty)
            raporty.append(raport)
            log.info("%s: %s ofert", nazwa, len(oferty))
        except Exception as e:  # noqa: BLE001 — jedno źródło nie może wywalić całości
            log.exception("%s: nieoczekiwany błąd", nazwa)
            raporty.append({
                "nazwa": nazwa, "ok": False, "liczba": 0,
                "uwaga": f"Błąd skryptu: {type(e).__name__}: {e}",
            })

    raporty.append({
        "nazwa": "licytacje.komornik.pl",
        "ok": False,
        "liczba": 0,
        "uwaga": "Nie scrapowane — rejestr jest aplikacją JS, filtry i stronicowanie "
                 "nie działają po stronie serwera. Służy do ręcznej weryfikacji terminu.",
    })

    log.info("Razem przed dedupem: %s", len(wszystkie))
    oferty = deduplikuj(wszystkie)
    log.info("Po dedupie: %s", len(oferty))

    # Mediana ceny za m² potrzebna do oceny perełek.
    ceny = sorted(o.cena_za_m2 for o in oferty if o.cena_za_m2)
    mediana = ceny[len(ceny) // 2] if ceny else None
    if mediana:
        log.info("Mediana ceny za m² w puli: %s zł", mediana)

    for o in oferty:
        ustal_perelke(o, mediana)
        ustal_flagi(o)

    przyjete, odrzucone = [], 0
    for o in oferty:
        powod = odrzucic(o)
        if powod:
            odrzucone += 1
            log.debug("Odrzucono %s (%s): %s", o.id, o.miasto, powod)
            continue
        stara = znane.get(o.id)
        o.pierwsze_wykrycie = (stara or {}).get("pierwsze_wykrycie") or dzis
        przyjete.append(o)

    przyjete.sort(key=klucz_sortowania)
    nowe = sum(1 for o in przyjete if o.pierwsze_wykrycie == dzis)
    log.info("Przyjęte: %s (nowe dziś: %s), odrzucone filtrem: %s",
             len(przyjete), nowe, odrzucone)

    if not przyjete and znane:
        log.error("Zero ofert po filtrach, a poprzednio było %s — "
                  "prawdopodobnie zmiana struktury portalu. Zachowuję stare dane.", len(znane))
        stan["ostrzezenie"] = (
            f"Przebieg {dzis} nie zwrócił żadnych ofert — dane poniżej są z "
            f"{(stan.get('wygenerowano') or '?')[:10]}. Sprawdź logi w GitHub Actions."
        )
        DATA_FILE.write_text(json.dumps(stan, ensure_ascii=False, indent=1), encoding="utf-8")
        return 1

    zapisz(przyjete, raporty, odrzucone)
    log.info("Wykonano %s żądań HTTP", pob.licznik)
    return 0


if __name__ == "__main__":
    sys.exit(main())

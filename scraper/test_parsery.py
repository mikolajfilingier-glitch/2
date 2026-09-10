"""
Testy na prawdziwych fragmentach tekstu pobranych z Adradara i ListyPrzetargow.
Nie ruszają sieci — sprawdzają wyłącznie logikę parsowania i filtrów.

Uruchomienie:  python scraper/test_parsery.py
"""

import sys
import datetime as dt
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from scrape import (  # noqa: E402
    Oferta, liczba_pln, metraz_z, data_iso, parsuj_adradar,
    odrzucic, ustal_flagi, ustal_perelke, deduplikuj, klucz_sortowania,
    dopasuj, FRAZY_UDZIAL_W_LOKALU, FRAZY_WEGIEL,
)

bledy = []


def sprawdz(opis, otrzymano, oczekiwano):
    if otrzymano == oczekiwano:
        print(f"  ok   {opis}")
    else:
        print(f"  BŁĄD {opis}: otrzymano {otrzymano!r}, oczekiwano {oczekiwano!r}")
        bledy.append(opis)


class FalszywyLink(dict):
    """Minimalny zamiennik tagu <a> — potrzebne tylko a['href']."""
    def __init__(self, href):
        super().__init__(href=href)


print("\n— liczby i daty —")
sprawdz("cena z twardą spacją", liczba_pln("131 315 zł"), 131315)
sprawdz("cena z groszami", liczba_pln("131 314,50 zł"), 131315)
sprawdz("cena wielomilionowa", liczba_pln("1 036 333,33 zł"), 1036333)
sprawdz("brak ceny", liczba_pln("Cena do negocjacji"), None)
sprawdz("metraż z przecinkiem", metraz_z("Pow.: 49,50 m2"), 49.5)
sprawdz("metraż z m²", metraz_z("53 m² 2 pokoje"), 53.0)
sprawdz("metraż działki odrzucony", metraz_z("1 795 m²"), None)
sprawdz("metraż kawalerki", metraz_z("20,70 m2"), 20.7)
sprawdz("data DD-MM-RRRR", data_iso("Wadium do 24-09-2026"), "2026-09-24")
sprawdz("data ISO", data_iso("Termin: 2026-10-13"), "2026-10-13")

print("\n— parsowanie bloku Adradara (prawdziwy tekst) —")
BLOK_KOCHLOWICE = (
    "Licytacja komornicza mieszkania Kochłowice, Ruda Śląska, TUNKLA "
    "...druga licytacja w trybie elektronicznym nieruchomości: LOKAL MIESZKALNY NR "
    "STANOWIĄCY ODRĘBNĄ NIERUCHOMOŚĆ WRAZ Z UDZIAŁEM W CZĘŚCI WSPÓLNEJ LOKAL MIESZKALNY "
    "Adres nieruchomości TUNKLA , 41-707 RUDA ŚLĄSKA, poczta Ruda Śląska "
    "Cena wywołania 130 000,00 zł (2/3 Szczegóły licytacji komorniczej "
    "Cena wywoławcza: 130 000 zł 2 469 zł/m² 53 m² 2 pokoje Termin: 2026-09-10 "
    "Organizator licytacji: KOMORNIK"
)
o = parsuj_adradar(BLOK_KOCHLOWICE, FalszywyLink("/przetarg/mieszkania/Kochlowice/licytacje_komornicze/17546215"),
                   "licytacje_komornicze", "17546215")
sprawdz("miasto", o.miasto, "Ruda Śląska")
sprawdz("dzielnica", o.dzielnica, "Kochłowice")
sprawdz("cena", o.cena_wywolawcza, 130000)
sprawdz("metraż", o.metraz, 53.0)
sprawdz("pokoje", o.pokoje, 2)
sprawdz("termin", o.data_licytacji, "2026-09-10")
sprawdz("cena za m²", o.cena_za_m2, 2453)
sprawdz("typ", o.typ_postepowania, "licytacja komornicza")

print("\n— odtworzenie metrażu z ceny za m², gdy portal go nie podał —")
BLOK_BEZ_METRAZU = (
    "Licytacja komornicza mieszkania Bytom, Karola Miarki "
    "...pierwsza licytacja nieruchomości: LOKAL MIESZKALNY "
    "Cena wywoławcza: 273 060 zł 2 128 zł/m² Termin: 2026-10-06 KOMORNIK"
)
o2 = parsuj_adradar(BLOK_BEZ_METRAZU, FalszywyLink("/przetarg/mieszkania/Bytom/licytacje_komornicze/1"),
                    "licytacje_komornicze", "1")
sprawdz("metraż odtworzony", o2.metraz is not None and 127 < o2.metraz < 130, True)

print("\n— odrzucanie: udział ułamkowy w lokalu —")
sprawdz(
    "udział 1/6 w spółdzielczym prawie do lokalu",
    bool(dopasuj(FRAZY_UDZIAL_W_LOKALU, "Przedmiotem licytacji jest 1/6 udziału w samodzielnym mieszkaniu")),
    True,
)
sprawdz(
    "udział 3/6 w mieszkaniu",
    bool(dopasuj(FRAZY_UDZIAL_W_LOKALU, "oferowany jest udział 3/6 w mieszkaniu o powierzchni 41,48 m²")),
    True,
)
sprawdz(
    "udział w CZĘŚCIACH WSPÓLNYCH nie odrzuca",
    bool(dopasuj(FRAZY_UDZIAL_W_LOKALU,
                 "lokal stanowiący odrębną nieruchomość wraz z udziałem 327/10000 "
                 "w częściach wspólnych budynku i gruntu")),
    False,
)
sprawdz(
    "udział 4/100 w nieruchomości wspólnej nie odrzuca",
    bool(dopasuj(FRAZY_UDZIAL_W_LOKALU,
                 "z udziałem 4/100 w nieruchomości wspólnej (grunt i części wspólne budynku)")),
    False,
)

print("\n— odrzucanie: ogrzewanie —")
sprawdz("piec węglowy odrzuca", bool(dopasuj(FRAZY_WEGIEL, "ogrzewanie: piec węglowy w kuchni")), True)
sprawdz("ogrzewanie piecowe NIE odrzuca", bool(dopasuj(FRAZY_WEGIEL, "ogrzewanie piecowe")), False)
sprawdz("piec gazowy NIE odrzuca", bool(dopasuj(FRAZY_WEGIEL, "ogrzewanie z pieca gazowego")), False)

print("\n— filtr twardy jako całość —")
przyszly_termin = (dt.date.today() + dt.timedelta(days=20)).isoformat()

tanie = Oferta(id="a", zrodlo="t", miasto="Bytom", cena_wywolawcza=124500, metraz=36.29,
               data_licytacji=przyszly_termin, opis="zadbany budynek z lat 80., dobry stan techniczny")
ustal_flagi(tanie)
sprawdz("tania oferta przechodzi", odrzucic(tanie), None)

zdewastowane = Oferta(id="b", zrodlo="t", miasto="Chorzów", cena_wywolawcza=101250, metraz=51.5,
                      data_licytacji=przyszly_termin,
                      opis="Lokal jest zdewastowany i wymaga generalnego remontu")
ustal_flagi(zdewastowane)
sprawdz("zdewastowany LOKAL przechodzi (atut cenowy)", odrzucic(zdewastowane), None)

rozbiorka = Oferta(id="c", zrodlo="t", miasto="Bytom", cena_wywolawcza=90000, metraz=50,
                   data_licytacji=przyszly_termin, opis="budynek wyłączony z użytkowania, do rozbiórki")
ustal_flagi(rozbiorka)
sprawdz("budynek do rozbiórki odrzucony", odrzucic(rozbiorka) is not None, True)

drogie = Oferta(id="d", zrodlo="t", miasto="Katowice", cena_wywolawcza=249150, metraz=46.5,
                data_licytacji=przyszly_termin, opis="")
ustal_flagi(drogie)
sprawdz("powyżej progu perełki odrzucone", odrzucic(drogie) is not None, True)

po_terminie = Oferta(id="e", zrodlo="t", miasto="Gliwice", cena_wywolawcza=120000, metraz=40,
                     data_licytacji="2026-01-01", opis="")
ustal_flagi(po_terminie)
sprawdz("po terminie odrzucone", odrzucic(po_terminie) is not None, True)

print("\n— perełki —")
mediana = 3000
przecietna_droga = Oferta(id="f", zrodlo="t", miasto="Zabrze", cena_wywolawcza=200000, metraz=52)
ustal_perelke(przecietna_droga, mediana)
sprawdz("przeciętna oferta 200 tys. nie jest perełką", przecietna_droga.perelka, False)
ustal_flagi(przecietna_droga)
sprawdz("i zostaje odrzucona", odrzucic(przecietna_droga) is not None, True)

okazja = Oferta(id="g", zrodlo="t", miasto="Bytom", cena_wywolawcza=194100, metraz=121.6)
ustal_perelke(okazja, mediana)
sprawdz("tania duża oferta jest perełką", okazja.perelka, True)

print("\n— deduplikacja —")
z_adradara = Oferta(id="h1", zrodlo="przetargi.adradar.pl", adres="ul. Tunkla",
                    miasto="Ruda Śląska", cena_wywolawcza=130000, metraz=53,
                    data_licytacji="2026-09-10", opis="krótki")
z_listy = Oferta(id="h2", zrodlo="listaprzetargow.pl", adres=None, miasto="Ruda Śląska",
                 cena_wywolawcza=130000, metraz=53, data_licytacji="2026-09-10",
                 wadium=13000, opis="dłuższy opis z portalu z dodatkowymi szczegółami")
scalone = deduplikuj([z_listy, z_adradara])
sprawdz("scalono do jednej oferty", len(scalone), 1)
sprawdz("adres z Adradara zachowany", scalone[0].adres, "ul. Tunkla")
sprawdz("wadium uzupełnione z drugiego źródła", scalone[0].wadium, 13000)
sprawdz("dłuższy opis wygrywa", scalone[0].opis.startswith("dłuższy"), True)
sprawdz("źródło dodatkowe zapisane", scalone[0].zrodla_dodatkowe, ["listaprzetargow.pl"])

print("\n— sortowanie —")
zielona = Oferta(id="s1", zrodlo="t", miasto="Bytom", cena_wywolawcza=150000, metraz=50,
                 opis="zadbany budynek, dobry stan techniczny")
czerwona = Oferta(id="s2", zrodlo="t", miasto="Bytom", cena_wywolawcza=60000, metraz=50,
                  opis="wymaga remontu po pożarze w części kuchennej")
for x in (zielona, czerwona):
    ustal_flagi(x)
posortowane = sorted([czerwona, zielona], key=klucz_sortowania)
sprawdz("czerwona flaga na końcu mimo niższej ceny", posortowane[0].id, "s1")

print("\n— flagi z opisu —")
pozar = Oferta(id="p", zrodlo="t", miasto="Sosnowiec", opis="wymaga remontu po pożarze w części kuchennej")
ustal_flagi(pozar)
sprawdz("pożar → czerwona", pozar.flaga_budynek["poziom"], "czerwona")

sluzebnosc = Oferta(id="sl", zrodlo="t", miasto="Sosnowiec",
                    opis="obciążona dożywotnią, nieodpłatną służebnością osobistą mieszkania")
ustal_flagi(sluzebnosc)
sprawdz("służebność → żółta", sluzebnosc.flaga_budynek["poziom"], "zolta")

pusty = Oferta(id="pu", zrodlo="t", miasto="Tychy", opis="")
ustal_flagi(pusty)
sprawdz("brak opisu → brak danych, nie zielona", pusty.flaga_budynek["poziom"], "brak")

miejskie = Oferta(id="mi", zrodlo="t", miasto="Tychy",
                  opis="pełne media, CO i ciepła woda z sieci miejskiej, instalacja gazowa")
ustal_flagi(miejskie)
sprawdz("ogrzewanie miejskie rozpoznane", miejskie.ogrzewanie, "miejskie / z sieci")
sprawdz("gaz rozpoznany", miejskie.media["gaz"], True)

print()
if bledy:
    print(f"NIEPOWODZENIE: {len(bledy)} testów nie przeszło")
    sys.exit(1)
print("Wszystkie testy przeszły.")

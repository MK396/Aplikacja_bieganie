"""PODGLAD SUROWYCH odpowiedzi API GIOS (v1) dla 5 stacji we Wroclawiu.
Nic nie zapisuje do bazy.

Dla kazdej stacji pokazuje po kolei, co ZWRACA API:
  1) station/findAll        - rekord stacji
  2) station/sensors/{id}   - lista stanowisk pomiarowych
  3) data/getData/{id}      - ostatnie wyniki dla stanowisk pylowych
  4) aqindex/getIndex/{id}  - indeks jakosci powietrza

Uruchomienie:  python3 scripts/podglad_gios.py
"""
import json
import time

import requests

BAZA = "https://api.gios.gov.pl/pjp-api/v1/rest"
KODY_STACJI = ("DsWrocBartni", "DsWrocNaGrob", "DsWrocWybCon", "DsWrocOrzech", "DsWrocAlWisn")
POZYCJE_PYLOWE = ("PM10", "PM2.5")

# False = pomija dlugie, powtarzalne pola "@context", "meta" i "links" (czytelniej)
# True  = pokazuje CALA odpowiedz dokladnie tak, jak przyszla z serwera
PELNA_ODPOWIEDZ = False
LICZBA_WYNIKOW = 5   # ile ostatnich godzin pokazac z data/getData


def pobierz(sciezka: str, **parametry) -> requests.Response:
    odpowiedz = requests.get(f"{BAZA}/{sciezka}", params=parametry, timeout=30)
    time.sleep(0.5)   # limit dla metadanych to 2 zapytania/min, wiec nie przesadzamy
    return odpowiedz


def pokaz(tytul: str, odpowiedz: requests.Response) -> None:
    print(f"\n--- {tytul}")
    print(f"    GET {odpowiedz.url}")
    print(f"    HTTP {odpowiedz.status_code}")
    try:
        dane = odpowiedz.json()
    except ValueError:
        print(odpowiedz.text[:500])
        return
    if not PELNA_ODPOWIEDZ and isinstance(dane, dict):
        dane = {k: v for k, v in dane.items() if k not in ("@context", "meta", "links")}
    print(json.dumps(dane, ensure_ascii=False, indent=2))


# 1) Lista stacji - to jedyne wywolanie "hurtowe"; pokazujemy tylko nasze 3 rekordy
odp = pobierz("station/findAll", size=500)
print(f"=== station/findAll: HTTP {odp.status_code}, {odp.url}")
wszystkie = odp.json()["Lista stacji pomiarowych"]
print(f"    (odpowiedz zawiera {len(wszystkie)} stacji z calej Polski; ponizej tylko 3 wybrane)")
nasze = [s for s in wszystkie if s["Kod stacji"] in KODY_STACJI]
print(json.dumps(nasze, ensure_ascii=False, indent=2))

for st in nasze:
    id_stacji = st["Identyfikator stacji"]
    print("\n" + "=" * 78)
    print(f"STACJA [{id_stacji}] {st['Nazwa stacji']}")
    print("=" * 78)

    # 2) Stanowiska (kazde stanowisko w jednej linii - lista bywa dluga)
    odp = pobierz(f"station/sensors/{id_stacji}")
    print(f"\n--- station/sensors/{id_stacji}")
    print(f"    GET {odp.url}\n    HTTP {odp.status_code}")
    klucz = "Lista stanowisk pomiarowych dla podanej stacji"
    stanowiska = odp.json().get(klucz, [])
    print(f'    "{klucz}": [{len(stanowiska)} stanowisk]')
    for sn in stanowiska:
        print("   ", json.dumps(sn, ensure_ascii=False))

    # 3) Dane dla stanowisk pylowych
    for sn in stanowiska:
        if sn["Wskaźnik - kod"] not in POZYCJE_PYLOWE:
            continue
        id_sn = sn["Identyfikator stanowiska"]
        pokaz(f"data/getData/{id_sn}  ({sn['Wskaźnik - kod']})",
              pobierz(f"data/getData/{id_sn}", size=LICZBA_WYNIKOW))

    # 4) Indeks jakosci powietrza
    pokaz(f"aqindex/getIndex/{id_stacji}", pobierz(f"aqindex/getIndex/{id_stacji}"))

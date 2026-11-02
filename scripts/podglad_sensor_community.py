"""Krok 3a: PODGLAD danych z Sensor.Community (nic nie zapisuje do bazy).

Uruchomienie:  python3 scripts/podglad_sensor_community.py
"""
import requests

# Prostokat obejmujacy Wroclaw: (lat_min, lon_min, lat_max, lon_max)
LAT_MIN, LON_MIN, LAT_MAX, LON_MAX = 50.98, 16.80, 51.22, 17.18

# Pobieramy tylko czujniki pylow z naszego prostokata (filtr po stronie serwera).
URL = (
    "https://data.sensor.community/airrohr/v1/filter/"
    f"type=SDS011&box={LAT_MIN},{LON_MIN},{LAT_MAX},{LON_MAX}"
)

odpowiedz = requests.get(URL, timeout=30)
odpowiedz.raise_for_status()
dane = odpowiedz.json()

print(f"Liczba rekordow: {len(dane)}\n")

# 1) Jak wyglada JEDEN surowy rekord
print("--- Surowy rekord (pierwszy) ---")
print(dane[0])

# 2) Przeksztalcamy do prostej postaci: jeden wiersz na czujnik (najnowszy odczyt)
najnowsze = {}
for rekord in dane:
    id_czujnika = rekord["sensor"]["id"]
    if id_czujnika not in najnowsze or rekord["timestamp"] > najnowsze[id_czujnika]["timestamp"]:
        najnowsze[id_czujnika] = rekord

print(f"\nLiczba unikalnych czujnikow: {len(najnowsze)}\n")
print(f"{'id':>8} {'lat':>9} {'lon':>9} {'PM2.5':>7} {'PM10':>7}  czas (UTC)")
for id_czujnika, rekord in najnowsze.items():
    wartosci = {w["value_type"]: w["value"] for w in rekord["sensordatavalues"]}
    lok = rekord["location"]
    print(
        f"{id_czujnika:>8} {float(lok['latitude']):>9.4f} {float(lok['longitude']):>9.4f} "
        f"{wartosci.get('P2', '-'):>7} {wartosci.get('P1', '-'):>7}  {rekord['timestamp']}"
    )

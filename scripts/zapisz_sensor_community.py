"""Krok 3b: pobiera dane z Sensor.Community i ZAPISUJE je do bazy PostGIS.

Uruchomienie (z folderu glownego projektu, przy dzialajacej bazie):
    .venv/bin/python scripts/zapisz_sensor_community.py
"""
import os
from datetime import datetime, timezone
from pathlib import Path

import psycopg
import requests

# Prostokat obejmujacy Wroclaw: (lat_min, lon_min, lat_max, lon_max)
LAT_MIN, LON_MIN, LAT_MAX, LON_MAX = 50.98, 16.80, 51.22, 17.18
URL = (
    "https://data.sensor.community/airrohr/v1/filter/"
    f"type=SDS011&box={LAT_MIN},{LON_MIN},{LAT_MAX},{LON_MAX}"
)
ZRODLO = "sensor_community"


def wczytaj_env(sciezka: Path) -> dict:
    """Prosty parser pliku .env (KLUCZ=wartosc), bez dodatkowych bibliotek."""
    wartosci = {}
    for linia in sciezka.read_text(encoding="utf-8").splitlines():
        linia = linia.strip()
        if linia and not linia.startswith("#") and "=" in linia:
            klucz, wartosc = linia.split("=", 1)
            wartosci[klucz.strip()] = wartosc.strip()
    return wartosci


def polacz_z_baza() -> psycopg.Connection:
    env = wczytaj_env(Path(__file__).resolve().parent.parent / ".env")
    return psycopg.connect(
        host="localhost",
        port=int(env.get("POSTGRES_PORT", 5432)),
        user=env["POSTGRES_USER"],
        password=env["POSTGRES_PASSWORD"],
        dbname=env["POSTGRES_DB"],
    )


def pobierz_najnowsze() -> list[dict]:
    """Zwraca po jednym (najnowszym) rekordzie na czujnik."""
    odpowiedz = requests.get(URL, timeout=30)
    odpowiedz.raise_for_status()
    najnowsze = {}
    for rekord in odpowiedz.json():
        if rekord["location"].get("indoor") == 1:   # czujniki wewnatrz budynkow pomijamy
            continue
        id_czujnika = str(rekord["sensor"]["id"])
        if id_czujnika not in najnowsze or rekord["timestamp"] > najnowsze[id_czujnika]["timestamp"]:
            najnowsze[id_czujnika] = rekord
    return list(najnowsze.values())


def na_liczbe(tekst):
    try:
        return float(tekst)
    except (TypeError, ValueError):
        return None


def zapisz(conn: psycopg.Connection, rekordy: list[dict]) -> tuple[int, int]:
    nowe_pomiary = 0
    with conn.cursor() as cur:
        for rekord in rekordy:
            id_czujnika = str(rekord["sensor"]["id"])
            lok = rekord["location"]
            lat, lon = na_liczbe(lok.get("latitude")), na_liczbe(lok.get("longitude"))
            if lat is None or lon is None:
                continue

            # 1) stacja: dodaj, a jesli juz jest - zaktualizuj polozenie
            cur.execute(
                """
                INSERT INTO stations (source, external_id, name, geom)
                VALUES (%s, %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326))
                ON CONFLICT (source, external_id)
                DO UPDATE SET geom = EXCLUDED.geom
                RETURNING station_id
                """,
                (ZRODLO, id_czujnika, f"SDS011 #{id_czujnika}", lon, lat),  # uwaga: lon PRZED lat
            )
            station_id = cur.fetchone()[0]

            # 2) pomiar: P1 = PM10, P2 = PM2.5
            wartosci = {w["value_type"]: na_liczbe(w["value"]) for w in rekord["sensordatavalues"]}
            czas = datetime.strptime(rekord["timestamp"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
            cur.execute(
                """
                INSERT INTO measurements (station_id, measured_at, pm25, pm10)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (station_id, measured_at) DO NOTHING
                """,
                (station_id, czas, wartosci.get("P2"), wartosci.get("P1")),
            )
            nowe_pomiary += cur.rowcount   # 1 jesli wstawiono, 0 jesli juz byl
    conn.commit()
    return len(rekordy), nowe_pomiary


if __name__ == "__main__":
    rekordy = pobierz_najnowsze()
    with polacz_z_baza() as conn:
        stacje, nowe = zapisz(conn, rekordy)
    print(f"Przetworzono stacji: {stacje}, nowych pomiarow zapisanych: {nowe}")

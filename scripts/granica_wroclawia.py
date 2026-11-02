"""Krok 6a: pobiera granice administracyjna Wroclawia z OpenStreetMap (Nominatim)
i zapisuje ja w bazie, w tabeli city_boundary.

Uruchomienie (z folderu glownego projektu, przy dzialajacej bazie):
    python scripts/granica_wroclawia.py
"""
import json

import requests

from zapisz_sensor_community import polacz_z_baza   # ponownie uzywamy polaczenia z bazą

URL = "https://nominatim.openstreetmap.org/search"
PARAMETRY = {
    "q": "Wrocław, Polska",
    "format": "jsonv2",
    "polygon_geojson": 1,   # popros o ksztalt granicy, nie tylko o punkt
    "limit": 5,
}
# Nominatim wymaga podania nazwy aplikacji w naglowku User-Agent
NAGLOWKI = {"User-Agent": "aplikacja-bieganie-projekt-studencki"}


def pobierz_granice() -> dict:
    """Zwraca geometrie (GeoJSON) granicy miasta."""
    odpowiedz = requests.get(URL, params=PARAMETRY, headers=NAGLOWKI, timeout=30)
    odpowiedz.raise_for_status()
    for wynik in odpowiedz.json():
        # szukamy obiektu typu 'relation' z powierzchnia (a nie punktem)
        if wynik["osm_type"] == "relation" and wynik["geojson"]["type"] in ("Polygon", "MultiPolygon"):
            print(f"Znaleziono: {wynik['display_name']}")
            return wynik["geojson"]
    raise RuntimeError("Nie znaleziono granicy Wroclawia w odpowiedzi Nominatim")


def zapisz(conn, geojson: dict) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS city_boundary (
                name TEXT PRIMARY KEY,
                geom geometry(MultiPolygon, 2180)
            )
            """
        )
        cur.execute(
            """
            INSERT INTO city_boundary (name, geom)
            VALUES (%s, ST_Transform(ST_Multi(ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326)), 2180))
            ON CONFLICT (name) DO UPDATE SET geom = EXCLUDED.geom
            """,
            ("Wrocław", json.dumps(geojson)),
        )
        cur.execute("SELECT round(ST_Area(geom) / 1e6) FROM city_boundary WHERE name = 'Wrocław'")
        print(f"Zapisano granice, powierzchnia: {cur.fetchone()[0]} km2")
    conn.commit()


if __name__ == "__main__":
    granica = pobierz_granice()
    with polacz_z_baza() as conn:
        zapisz(conn, granica)

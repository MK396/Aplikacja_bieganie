"""Krok 6b: mapa luk w pokryciu czujnikami. Czyta dane Z BAZY (nie z API).

Pokazuje: granice Wroclawia, czujniki oraz punkty siatki (co 500 m) pokolorowane
wedlug odleglosci do najbliższego czujnika.

Uruchomienie (z aktywnym .venv i dzialajaca baza):
    python scripts/mapa_luk.py
Mapa otworzy sie pod http://localhost:8001/mapa_luk.html (Ctrl+C konczy serwer).
"""
import json
import webbrowser
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from zapisz_sensor_community import polacz_z_baza

PLIK_WYJSCIOWY = Path(__file__).resolve().parent.parent / "output" / "mapa_luk.html"


def pobierz_dane() -> dict:
    with polacz_z_baza() as conn, conn.cursor() as cur:
        cur.execute("SELECT ST_AsGeoJSON(ST_Transform(geom, 4326)) FROM city_boundary LIMIT 1")
        granica = json.loads(cur.fetchone()[0])

        cur.execute("SELECT external_id, ST_Y(geom), ST_X(geom) FROM stations")
        czujniki = [{"id": i, "lat": lat, "lon": lon} for i, lat, lon in cur.fetchall()]

        # punkty siatki przeliczamy z metrow (2180) z powrotem na GPS (4326) dla mapy
        cur.execute(
            """
            SELECT ST_Y(ST_Transform(geom, 4326)), ST_X(ST_Transform(geom, 4326)), dist_m
            FROM grid_points
            """
        )
        siatka = [{"lat": lat, "lon": lon, "d": round(d)} for lat, lon, d in cur.fetchall()]
    return {"granica": granica, "czujniki": czujniki, "siatka": siatka}


SZABLON = """<!DOCTYPE html>
<html lang="pl">
<head>
  <meta charset="utf-8">
  <title>Luki w pokryciu czujnikami - Wroclaw</title>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <style>
    html, body, #mapa { height: 100%; margin: 0; }
    .legenda { background: white; padding: 8px 10px; line-height: 1.5; border-radius: 4px; }
    .legenda i { display: inline-block; width: 14px; height: 14px; margin-right: 6px; vertical-align: middle; }
  </style>
</head>
<body>
<div id="mapa"></div>
<script>
  const dane = __DANE__;

  const mapa = L.map('mapa').setView([51.11, 17.03], 12);
  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '&copy; OpenStreetMap contributors'
  }).addTo(mapa);

  L.geoJSON(dane.granica, {style: {color: '#333', weight: 2, fill: false}}).addTo(mapa);

  // Kolor wedlug odleglosci do najblizszego czujnika (w metrach)
  function kolor(d) {
    if (d <= 1000) return '#2ecc71';
    if (d <= 2000) return '#f1c40f';
    if (d <= 3000) return '#e67e22';
    return '#e74c3c';
  }

  dane.siatka.forEach(p => {
    // L.circle ma promien w METRACH (250 m = polowa kroku siatki), wiec skaluje sie z mapa
    L.circle([p.lat, p.lon], {
      radius: 250, stroke: false, fillColor: kolor(p.d), fillOpacity: 0.55
    }).addTo(mapa).bindPopup('Najblizszy czujnik: ' + p.d + ' m');
  });

  dane.czujniki.forEach(c => {
    L.circleMarker([c.lat, c.lon], {
      radius: 5, color: '#000', weight: 1, fillColor: '#3388ff', fillOpacity: 1
    }).addTo(mapa).bindPopup('Czujnik #' + c.id);
  });

  const legenda = L.control({position: 'bottomright'});
  legenda.onAdd = function () {
    const div = L.DomUtil.create('div', 'legenda');
    div.innerHTML = '<b>Odleglosc do czujnika</b><br>' +
      '<i style="background:#2ecc71"></i>do 1 km<br>' +
      '<i style="background:#f1c40f"></i>1-2 km<br>' +
      '<i style="background:#e67e22"></i>2-3 km<br>' +
      '<i style="background:#e74c3c"></i>powyzej 3 km<br>' +
      '<i style="background:#3388ff"></i>czujnik<br>' +
      '<small>Czujnikow: ' + dane.czujniki.length + '<br>Punktow siatki: ' + dane.siatka.length + '</small>';
    return div;
  };
  legenda.addTo(mapa);
</script>
</body>
</html>
"""


if __name__ == "__main__":
    dane = pobierz_dane()
    PLIK_WYJSCIOWY.parent.mkdir(exist_ok=True)
    PLIK_WYJSCIOWY.write_text(SZABLON.replace("__DANE__", json.dumps(dane)), encoding="utf-8")
    print(f"Czujnikow: {len(dane['czujniki'])}, punktow siatki: {len(dane['siatka'])}")

    port = 8001   # inny niz mapa_czujnikow.py (8000), zeby mozna bylo miec obie naraz
    serwer = ThreadingHTTPServer(
        ("127.0.0.1", port), partial(SimpleHTTPRequestHandler, directory=str(PLIK_WYJSCIOWY.parent))
    )
    adres = f"http://localhost:{port}/{PLIK_WYJSCIOWY.name}"
    print(f"Mapa dziala pod adresem: {adres}\nZatrzymanie: Ctrl+C")
    webbrowser.open(adres)
    try:
        serwer.serve_forever()
    except KeyboardInterrupt:
        print("\nZatrzymano serwer.")

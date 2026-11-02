"""Generuje plik HTML z mapa Wroclawia i polozeniem czujnikow Sensor.Community.
Niczego nie zapisuje do bazy.

Uruchomienie:  python3 scripts/mapa_czujnikow.py
Skrypt sam otworzy mape w przegladarce pod http://localhost:8000/mapa_czujnikow.html
(przegladarka potrzebuje internetu - pobiera kafelki mapy i biblioteke Leaflet).
Zatrzymanie serwera: Ctrl+C w terminalu.
"""
import json
import webbrowser
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import requests

# Prostokat obejmujacy Wroclaw: (lat_min, lon_min, lat_max, lon_max)
LAT_MIN, LON_MIN, LAT_MAX, LON_MAX = 50.98, 16.80, 51.22, 17.18
URL = (
    "https://data.sensor.community/airrohr/v1/filter/"
    f"type=SDS011&box={LAT_MIN},{LON_MIN},{LAT_MAX},{LON_MAX}"
)
PLIK_WYJSCIOWY = Path(__file__).resolve().parent.parent / "output" / "mapa_czujnikow.html"


def pobierz_czujniki() -> list[dict]:
    """Po jednym (najnowszym) odczycie na czujnik, jako prosta lista slownikow."""
    odpowiedz = requests.get(URL, timeout=30)
    odpowiedz.raise_for_status()
    najnowsze = {}
    for rekord in odpowiedz.json():
        if rekord["location"].get("indoor") == 1:
            continue
        id_czujnika = rekord["sensor"]["id"]
        if id_czujnika not in najnowsze or rekord["timestamp"] > najnowsze[id_czujnika]["timestamp"]:
            najnowsze[id_czujnika] = rekord

    czujniki = []
    for id_czujnika, rekord in najnowsze.items():
        wartosci = {w["value_type"]: w["value"] for w in rekord["sensordatavalues"]}
        czujniki.append({
            "id": id_czujnika,
            "lat": float(rekord["location"]["latitude"]),
            "lon": float(rekord["location"]["longitude"]),
            "pm25": float(wartosci["P2"]) if "P2" in wartosci else None,
            "pm10": float(wartosci["P1"]) if "P1" in wartosci else None,
            "czas": rekord["timestamp"],
        })
    return czujniki


SZABLON = """<!DOCTYPE html>
<html lang="pl">
<head>
  <meta charset="utf-8">
  <title>Czujniki Sensor.Community - Wroclaw</title>
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
  const czujniki = __DANE__;

  const mapa = L.map('mapa').setView([51.11, 17.03], 12);
  // Uwaga: tile.openstreetmap.org blokuje strony otwierane z dysku (file://),
  // dlatego skrypt serwuje te strone przez http://localhost.
  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '&copy; OpenStreetMap contributors'
  }).addTo(mapa);

  // Kolor wedlug PM2.5 (progi zblizone do skali EEA)
  function kolor(pm25) {
    if (pm25 === null) return '#808080';
    if (pm25 <= 5)  return '#2ecc71';
    if (pm25 <= 15) return '#a3d633';
    if (pm25 <= 50) return '#f1c40f';
    if (pm25 <= 90) return '#e67e22';
    return '#e74c3c';
  }

  czujniki.forEach(c => {
    L.circleMarker([c.lat, c.lon], {
      radius: 8, color: '#333', weight: 1, fillColor: kolor(c.pm25), fillOpacity: 0.9
    }).addTo(mapa).bindPopup(
      '<b>Czujnik #' + c.id + '</b><br>' +
      'PM2.5: ' + (c.pm25 === null ? '-' : c.pm25.toFixed(1)) + ' &micro;g/m&sup3;<br>' +
      'PM10: ' + (c.pm10 === null ? '-' : c.pm10.toFixed(1)) + ' &micro;g/m&sup3;<br>' +
      '<small>' + c.czas + ' UTC</small>'
    );
  });

  const legenda = L.control({position: 'bottomright'});
  legenda.onAdd = function () {
    const div = L.DomUtil.create('div', 'legenda');
    div.innerHTML = '<b>PM2.5 (&micro;g/m&sup3;)</b><br>' +
      '<i style="background:#2ecc71"></i>0-5<br>' +
      '<i style="background:#a3d633"></i>5-15<br>' +
      '<i style="background:#f1c40f"></i>15-50<br>' +
      '<i style="background:#e67e22"></i>50-90<br>' +
      '<i style="background:#e74c3c"></i>&gt;90<br>' +
      '<i style="background:#808080"></i>brak<br>' +
      '<small>Czujnikow: ' + czujniki.length + '</small>';
    return div;
  };
  legenda.addTo(mapa);
</script>
</body>
</html>
"""


if __name__ == "__main__":
    czujniki = pobierz_czujniki()
    PLIK_WYJSCIOWY.parent.mkdir(exist_ok=True)
    PLIK_WYJSCIOWY.write_text(SZABLON.replace("__DANE__", json.dumps(czujniki)), encoding="utf-8")
    print(f"Czujnikow: {len(czujniki)}\nZapisano: {PLIK_WYJSCIOWY}")

    # Mini serwer lokalny: strona z http://localhost wysyla Referer, ktorego wymaga OSM.
    port = 8000
    folder = str(PLIK_WYJSCIOWY.parent)
    serwer = ThreadingHTTPServer(("127.0.0.1", port), partial(SimpleHTTPRequestHandler, directory=folder))
    adres = f"http://localhost:{port}/{PLIK_WYJSCIOWY.name}"
    print(f"Mapa dziala pod adresem: {adres}\nZatrzymanie: Ctrl+C")
    webbrowser.open(adres)
    try:
        serwer.serve_forever()
    except KeyboardInterrupt:
        print("\nZatrzymano serwer.")

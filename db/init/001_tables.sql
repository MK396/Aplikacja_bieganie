-- Krok 2: tabele stacji i pomiarow

-- Rozszerzenie PostGIS (typy i funkcje przestrzenne)
CREATE EXTENSION IF NOT EXISTS postgis;

-- ---------------------------------------------------------------
-- STACJE: gdzie stoi czujnik (jeden wiersz = jeden czujnik)
-- ---------------------------------------------------------------
CREATE TABLE stations (
    station_id   SERIAL PRIMARY KEY,           -- nasz wlasny numer
    source       TEXT NOT NULL,                -- skad: 'sensor_community', 'gios', 'open_meteo'
    external_id  TEXT NOT NULL,                -- numer czujnika w systemie zrodla
    name         TEXT,                         -- opcjonalna nazwa
    geom         geometry(Point, 4326) NOT NULL, -- polozenie (lon, lat)
    UNIQUE (source, external_id)               -- ten sam czujnik nie moze wystapic 2 razy
);

-- Indeks przestrzenny GIST: przyspiesza zapytania "co jest w poblizu"
CREATE INDEX stations_geom_gist ON stations USING GIST (geom);

-- ---------------------------------------------------------------
-- POMIARY: co czujnik zmierzyl i kiedy (jeden wiersz = jeden odczyt)
-- ---------------------------------------------------------------
CREATE TABLE measurements (
    station_id   INT NOT NULL REFERENCES stations (station_id) ON DELETE CASCADE,
    measured_at  TIMESTAMPTZ NOT NULL,         -- czas pomiaru (ze strefa czasowa)
    pm25         REAL,                         -- PM2.5 w ug/m3 (moze byc brak)
    pm10         REAL,                         -- PM10 w ug/m3 (moze byc brak)
    PRIMARY KEY (station_id, measured_at)      -- 1 odczyt na czujnik na moment
);

-- Indeks po czasie: szybkie "daj najnowsze pomiary"
CREATE INDEX measurements_time_idx ON measurements (measured_at DESC);

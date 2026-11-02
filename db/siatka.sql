-- Etap 6: siatka punktow i luki w pokryciu czujnikami.
--
-- NIE jest w db/init/, bo wymaga danych w bazie. Uruchom RECZNIE, gdy sa juz:
--   1) stacje:  python scripts/zapisz_sensor_community.py
--   2) granica: python scripts/granica_wroclawia.py   (tabela city_boundary)
-- Komenda (z folderu glownego projektu):
--   docker compose exec -T db psql -U aq -d aq < db/siatka.sql
--
-- Plik mozna uruchamiac wielokrotnie (np. po dodaniu nowych stacji):
-- siatka jest budowana od nowa, a odleglosci przeliczane.

-- 1) Wspolrzedne stacji w metrach (EPSG:2180), liczone automatycznie z geom.
ALTER TABLE stations
    ADD COLUMN IF NOT EXISTS geom_2180 geometry(Point, 2180)
    GENERATED ALWAYS AS (ST_Transform(geom, 2180)) STORED;

CREATE INDEX IF NOT EXISTS stations_geom_2180_gist ON stations USING GIST (geom_2180);

-- 2) Siatka punktow co 500 m w prostokacie obejmujacym Wroclaw (w metrach, EPSG:2180).
DROP TABLE IF EXISTS grid_points;

CREATE TABLE grid_points (
    grid_id SERIAL PRIMARY KEY,
    geom    geometry(Point, 2180),
    dist_m  REAL            -- odleglosc do najblizszego czujnika [m]
);

INSERT INTO grid_points (geom)
SELECT ST_SetSRID(ST_MakePoint(x, y), 2180)
FROM (SELECT ST_Transform(ST_MakeEnvelope(16.80, 50.98, 17.18, 51.22, 4326), 2180) AS b) e,
     generate_series(floor(ST_XMin(b) / 500)::int * 500, ceil(ST_XMax(b))::int, 500) AS x,
     generate_series(floor(ST_YMin(b) / 500)::int * 500, ceil(ST_YMax(b))::int, 500) AS y;

CREATE INDEX grid_points_geom_gist ON grid_points USING GIST (geom);

-- 3) Przyciecie do granic administracyjnych Wroclawia.
DELETE FROM grid_points g
WHERE NOT EXISTS (
    SELECT 1 FROM city_boundary b WHERE ST_Within(g.geom, b.geom)
);

-- 4) Odleglosc kazdego punktu do najblizszego czujnika
--    (operator <-> + indeks GiST wybiera najblizszy, ST_Distance liczy metry).
UPDATE grid_points g
SET dist_m = n.d
FROM (
    SELECT g2.grid_id, s.d
    FROM grid_points g2
    CROSS JOIN LATERAL (
        SELECT ST_Distance(g2.geom, st.geom_2180) AS d
        FROM stations st
        ORDER BY g2.geom <-> st.geom_2180
        LIMIT 1
    ) s
) n
WHERE g.grid_id = n.grid_id;

-- Podsumowanie: ile punktow siatki w przedzialach odleglosci co 500 m
-- (1 = 0-500 m, 2 = 500-1000 m, ..., 11 = powyzej 5 km).
SELECT width_bucket(dist_m, 0, 5000, 10) AS przedzial, count(*)
FROM grid_points GROUP BY 1 ORDER BY 1;

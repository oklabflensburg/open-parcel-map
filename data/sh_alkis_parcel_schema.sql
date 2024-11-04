-- TABELLE ALKIS FLURSTUECKE SCHLESWIG-HOLSTEIN
DROP TABLE IF EXISTS sh_alkis_parcel CASCADE;

CREATE TABLE IF NOT EXISTS sh_alkis_parcel (
  id SERIAL,
  adv_id VARCHAR,
  beginnt TIMESTAMP WITH TIME ZONE,
  land VARCHAR,
  regierungsbezirk INT,
  kreis INT,
  gemeinde VARCHAR,
  gemarkungsnummer INT,
  flurnummer INT,
  nenner INT,
  zaehler INT,
  abweichender_rechtszustand BOOLEAN,
  wkb_geometry GEOMETRY(POLYGON, 4326),
  PRIMARY KEY(id)
);


-- UNIQUE INDEX
CREATE UNIQUE INDEX IF NOT EXISTS sh_alkis_parcel_adv_id_idx ON sh_alkis_parcel (adv_id);

-- GEOMETRY INDEX
CREATE INDEX IF NOT EXISTS sh_alkis_parcel_wkb_geometry_idx ON sh_alkis_parcel USING GIST (wkb_geometry);

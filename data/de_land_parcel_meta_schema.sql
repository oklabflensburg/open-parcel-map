-- HILFSTABELLE GEMARKUNGEN DEUTSCHLAND
DROP TABLE IF EXISTS de_land_parcel_meta CASCADE;

CREATE TABLE IF NOT EXISTS de_land_parcel_meta (
  id SERIAL,
  ags INT,
  gemeindename VARCHAR,
  gemarkungsnummer INT,
  gemarkungsname VARCHAR,
  PRIMARY KEY(id)
);


-- INDEX
CREATE INDEX IF NOT EXISTS de_land_parcel_meta_ags_id_idx ON de_land_parcel_meta (ags);
CREATE INDEX IF NOT EXISTS de_land_parcel_meta_gemarkungsnummer_id_idx ON de_land_parcel_meta (gemarkungsnummer);
CREATE INDEX IF NOT EXISTS de_land_parcel_meta_gemarkungsname_id_idx ON de_land_parcel_meta (gemarkungsname);

-- UNIQUE INDEX
CREATE UNIQUE INDEX IF NOT EXISTS de_land_parcel_meta_ags_gemarkungsnummer_id_idx ON de_land_parcel_meta (ags, gemarkungsnummer);

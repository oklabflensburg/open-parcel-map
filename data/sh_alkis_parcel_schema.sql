-- TABELLE ALKIS FLURSTUECKE SCHLESWIG-HOLSTEIN
DROP TABLE IF EXISTS sh_alkis_parcel CASCADE;

CREATE TABLE IF NOT EXISTS sh_alkis_parcel (
  id SERIAL PRIMARY KEY,
  adv_id VARCHAR,
  state_number VARCHAR,
  county_number INT,
  municipality_name VARCHAR,
  administrative_district_number INT,
  cadastral_district_number INT NOT NULL,
  parcel_number TEXT GENERATED ALWAYS AS (
    CASE
      WHEN numerator IS NULL AND denominator IS NULL THEN NULL
      WHEN denominator IS NULL THEN numerator::text
      ELSE numerator::text || '/' || denominator::text
    END
  ) STORED,
  field_number_original VARCHAR,
  field_number TEXT GENERATED ALWAYS AS (
    LPAD(field_number_original, 3, '0')
  ) STORED,
  denominator INT,
  numerator INT,
  different_legal_status BOOLEAN,
  start_time TIMESTAMP WITH TIME ZONE,
  wkb_geometry GEOMETRY(POLYGON, 4326)
);


-- UNIQUE INDEX
CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_parcel ON sh_alkis_parcel (
  adv_id,
  cadastral_district_number,
  parcel_number
);

-- GIN INDEX
CREATE INDEX IF NOT EXISTS idx_sh_alkis_parcel_number_text ON sh_alkis_parcel ((parcel_number::TEXT));

-- GEOMETRY INDEX
CREATE INDEX IF NOT EXISTS idx_sh_alkis_parcel_geometry ON sh_alkis_parcel USING GIST (wkb_geometry);

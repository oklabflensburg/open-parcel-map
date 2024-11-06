-- HILFSTABELLE GEMARKUNGEN DEUTSCHLAND
DROP TABLE IF EXISTS de_cadastral_district_meta CASCADE;

CREATE TABLE IF NOT EXISTS de_cadastral_district_meta (
    id SERIAL PRIMARY KEY,
    official_municipality_key VARCHAR(8),
    cadastral_district_number INT,
    cadastral_district_name VARCHAR,
    municipality_name VARCHAR,
    combined_gin TEXT GENERATED ALWAYS AS (
        cadastral_district_name || ' ' || municipality_name || ' ' || official_municipality_key::TEXT
    ) STORED
);

-- INDEXES
CREATE INDEX IF NOT EXISTS idx_official_muni_key ON de_cadastral_district_meta (official_municipality_key);
CREATE INDEX IF NOT EXISTS idx_cadastral_district_num ON de_cadastral_district_meta (cadastral_district_number);

-- GIN INDEXES
CREATE INDEX IF NOT EXISTS idx_municipality_name_trgm ON de_cadastral_district_meta USING GIN (municipality_name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_cadastral_district_name_trgm ON de_cadastral_district_meta USING GIN (cadastral_district_name gin_trgm_ops);


-- UNIQUE INDEX
CREATE UNIQUE INDEX IF NOT EXISTS idx_uniq_muni_key_district_num ON de_cadastral_district_meta (
    official_municipality_key, 
    cadastral_district_number
);

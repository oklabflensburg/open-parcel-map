#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Command line tool to import ALKIS (NAS/GML) parcels into PostGIS.

The script expects Schleswig-Holstein ALKIS extracts (``AX_Flurstueck`` features)
stored as ``.xml`` or ``.xml.gz`` files. It reads each parcel, converts the raw
GML geometry via ``ST_GeomFromGML`` and inserts the attributes into the
``sh_alkis_parcel`` table that is shipped with this repository.

Usage example::

    python tools/insert_alkis_gml.py --env ../.env --input ../data/sh/alkis/01_2025

The script keeps memory usage low by streaming the XML files with
``xml.etree.ElementTree.iterparse`` and commits in configurable batches.
"""

from __future__ import annotations

import logging
import os
import sys
import traceback
import typing as t
import xml.etree.ElementTree as ET

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import click
import psycopg2
from dotenv import load_dotenv
from psycopg2.extensions import connection as PsycopgConnection
from psycopg2.extensions import cursor as PsycopgCursor
from psycopg2.extras import execute_values
from psycopg2.sql import SQL, Identifier


# Element namespaces used in NAS/GML files.
NS = {
    "adv": "http://www.adv-online.de/namespaces/adv/gid/7.1",
    "gml": "http://www.opengis.net/gml/3.2",
}


ADV_FLURSTUECK = f"{{{NS['adv']}}}AX_Flurstueck"


@dataclass
class ImportStats:
    files_seen: int = 0
    parcels_seen: int = 0
    parcels_inserted: int = 0
    parcels_skipped: int = 0
    errors: int = 0


def log_exceptions(exc_type, exc_value, exc_traceback):
    """Log unhandled exceptions before letting Python terminate."""

    for line in traceback.TracebackException(exc_type, exc_value, exc_traceback).format(chain=True):
        logging.exception(line)

    logging.exception(exc_value)
    sys.__excepthook__(exc_type, exc_value, exc_traceback)


def configure_logging(verbose: bool, debug: bool) -> None:
    level = logging.DEBUG if debug else logging.INFO if verbose else logging.WARNING
    logging.basicConfig(format="%(levelname)s: %(message)s", level=level)


def load_env(env_path: Path) -> PsycopgConnection:
    """Load a .env file and return a Postgres connection."""

    if not env_path.exists():
        raise FileNotFoundError(f".env file not found: {env_path}")

    load_dotenv(dotenv_path=env_path)

    conn = psycopg2.connect(
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASS"),
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
    )

    conn.autocommit = False
    logging.info("database connection established")
    return conn


def iter_flurstuecke(path: Path) -> t.Iterator[ET.Element]:
    """Yield ``AX_Flurstueck`` elements from an ALKIS NAS/GML file."""

    opener: t.Callable[..., t.Iterator[bytes]]

    if path.suffix == ".gz":
        import gzip

        opener = lambda p: gzip.open(p, "rb")  # noqa: E731 - small helper
    else:
        opener = lambda p: open(p, "rb")  # noqa: E731 - small helper

    logging.debug("parsing file %s", path)

    with opener(path) as fh:  # type: ignore[arg-type]
        try:
            for event, elem in ET.iterparse(fh, events=("end",)):
                if elem.tag == ADV_FLURSTUECK:
                    yield elem
                    elem.clear()
        except OSError as error:
            # Schleswig-Holstein files contain an extra newline after the
            # compressed stream; ``gzip`` raises ``Not a gzipped file`` at EOF.
            if "Not a gzipped file" in str(error):
                logging.debug("ignoring gzip trailer issue for %s", path)
            else:
                raise


def find_text(element: ET.Element, path: str) -> t.Optional[str]:
    node = element.find(path, NS)
    if node is None or node.text is None:
        return None
    value = node.text.strip()
    return value or None


def parse_int(value: t.Optional[str]) -> t.Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        logging.debug("failed to parse int from %s", value)
        return None


def parse_bool(value: t.Optional[str]) -> t.Optional[bool]:
    if value is None:
        return None
    lowered = value.strip().lower()
    if lowered in {"true", "1", "t", "yes"}:
        return True
    if lowered in {"false", "0", "f", "no"}:
        return False
    logging.debug("unexpected boolean literal: %s", value)
    return None


def parse_datetime(value: t.Optional[str]) -> t.Optional[datetime]:
    if value is None:
        return None
    try:
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        return datetime.fromisoformat(value)
    except ValueError:
        logging.debug("failed to parse datetime: %s", value)
    return None


def parse_poslist(text: str, dimension: t.Optional[int]) -> list[tuple[float, float]]:
    try:
        raw = [float(item) for item in text.split()]
    except ValueError:
        logging.debug("failed to parse posList: %s", text[:64])
        return []

    dim = dimension or 2

    if dim < 2:
        dim = 2

    if len(raw) % dim != 0:
        logging.debug("unexpected coordinate count %s for dimension %s", len(raw), dim)
        return []

    coords: list[tuple[float, float]] = []

    for index in range(0, len(raw), dim):
        coords.append((raw[index], raw[index + 1]))

    return coords


def parse_segment(segment: ET.Element) -> list[tuple[float, float]]:
    pos_list = segment.find("gml:posList", NS)

    if pos_list is not None and pos_list.text:
        dimension = pos_list.get("srsDimension") or segment.get("srsDimension")
        return parse_poslist(pos_list.text, int(dimension) if dimension else None)

    positions = [pos.text for pos in segment.findall("gml:pos", NS) if pos.text]

    if positions:
        coords: list[tuple[float, float]] = []
        for pos in positions:
            coords.extend(parse_poslist(pos, None))
        return coords

    coords_text = segment.findtext("gml:coordinates", default=None, namespaces=NS)
    if coords_text:
        return parse_poslist(coords_text.replace(",", " "), None)

    return []


def append_curve_points(
    current: list[tuple[float, float]], curve: ET.Element
) -> list[tuple[float, float]]:
    segments = curve.find("gml:segments", NS)

    if segments is None:
        return current

    for segment in segments:
        points = parse_segment(segment)

        if not points:
            continue

        if current:
            if current[-1] == points[0]:
                current.extend(points[1:])
            else:
                current.extend(points)
        else:
            current.extend(points)

    return current


def ring_coordinates(ring: ET.Element) -> list[tuple[float, float]]:
    coords: list[tuple[float, float]] = []

    for curve_member in ring.findall("gml:curveMember", NS):
        curve = curve_member.find("gml:Curve", NS)
        if curve is None:
            href = curve_member.get("{http://www.w3.org/1999/xlink}href")
            if href:
                logging.debug("curve references via xlink are not supported: %s", href)
            continue
        coords = append_curve_points(coords, curve)

    if coords and coords[0] != coords[-1]:
        coords.append(coords[0])

    if len(coords) < 4:
        logging.debug("ring has insufficient points (%s)", len(coords))
        return []

    return coords


def polygon_patch_to_rings(patch: ET.Element) -> t.Optional[tuple[list[tuple[float, float]], list[list[tuple[float, float]]]]]:
    exterior_ring = patch.find("gml:exterior/gml:Ring", NS)

    if exterior_ring is None:
        return None

    exterior = ring_coordinates(exterior_ring)

    if not exterior:
        return None

    interiors: list[list[tuple[float, float]]] = []

    for interior_ring in patch.findall("gml:interior/gml:Ring", NS):
        ring = ring_coordinates(interior_ring)
        if ring:
            interiors.append(ring)

    return exterior, interiors


def surface_to_polygons(surface: ET.Element) -> list[tuple[list[tuple[float, float]], list[list[tuple[float, float]]]]]:
    patches = surface.find("gml:patches", NS)

    if patches is None:
        return []

    polygons: list[tuple[list[tuple[float, float]], list[list[tuple[float, float]]]]] = []

    for patch in patches.findall("gml:PolygonPatch", NS):
        rings = polygon_patch_to_rings(patch)
        if rings:
            polygons.append(rings)

    return polygons


def geometry_to_polygons(geometry: ET.Element) -> list[tuple[list[tuple[float, float]], list[list[tuple[float, float]]]]]:
    polygons: list[tuple[list[tuple[float, float]], list[list[tuple[float, float]]]]] = []

    if geometry.tag == "{http://www.opengis.net/gml/3.2}MultiSurface":
        for member in geometry.findall("gml:surfaceMember", NS):
            surface = member.find("gml:Surface", NS)
            if surface is not None:
                polygons.extend(surface_to_polygons(surface))
    elif geometry.tag == "{http://www.opengis.net/gml/3.2}Surface":
        polygons.extend(surface_to_polygons(geometry))
    elif geometry.tag == "{http://www.opengis.net/gml/3.2}Polygon":
        rings = polygon_patch_to_rings(geometry)
        if rings:
            polygons.append(rings)

    return polygons


def ring_to_wkt(ring: list[tuple[float, float]]) -> str:
    return ", ".join(f"{x} {y}" for x, y in ring)


def polygon_to_wkt(
    exterior: list[tuple[float, float]],
    holes: list[list[tuple[float, float]]],
) -> str:
    rings = [f"({ring_to_wkt(exterior)})"]
    for hole in holes:
        rings.append(f"({ring_to_wkt(hole)})")
    return ", ".join(rings)


def polygons_to_wkt(
    polygons: list[tuple[list[tuple[float, float]], list[list[tuple[float, float]]]]]
) -> t.Optional[str]:
    if not polygons:
        return None

    if len(polygons) == 1:
        exterior, holes = polygons[0]
        return f"POLYGON({polygon_to_wkt(exterior, holes)})"

    polygon_wkts = []
    for exterior, holes in polygons:
        polygon_wkts.append(f"({polygon_to_wkt(exterior, holes)})")

    joined = ", ".join(polygon_wkts)
    return f"MULTIPOLYGON({joined})"


def extract_parcel(element: ET.Element) -> t.Optional[dict[str, t.Any]]:
    """Convert an ``AX_Flurstueck`` XML element into a dict for SQL inserts."""

    adv_id = find_text(element, "./gml:identifier")
    geometry_node = element.find(".//gml:MultiSurface", NS)

    if geometry_node is None:
        geometry_node = element.find(".//gml:Surface", NS)

    if geometry_node is None:
        geometry_node = element.find(".//gml:Polygon", NS)

    geometry_wkt: t.Optional[str] = None

    if geometry_node is not None:
        polygons = geometry_to_polygons(geometry_node)
        geometry_wkt = polygons_to_wkt(polygons)

    if geometry_wkt is None:
        logging.debug("skipping parcel %s without supported geometry", adv_id)
        return None

    data = {
        "adv_id": adv_id,
        "start_time": parse_datetime(
            find_text(element, "./adv:lebenszeitintervall/adv:AA_Lebenszeitintervall/adv:beginnt")
        ),
        "state_number": find_text(
            element, "./adv:gemeindezugehoerigkeit/adv:AX_Gemeindekennzeichen/adv:land"
        ),
        "administrative_district_number": parse_int(
            find_text(element, "./adv:gemeindezugehoerigkeit/adv:AX_Gemeindekennzeichen/adv:regierungsbezirk")
        ),
        "county_number": parse_int(
            find_text(element, "./adv:gemeindezugehoerigkeit/adv:AX_Gemeindekennzeichen/adv:kreis")
        ),
        "municipality_number": parse_int(
            find_text(element, "./adv:gemeindezugehoerigkeit/adv:AX_Gemeindekennzeichen/adv:gemeinde")
        ),
        "cadastral_district_number": parse_int(
            find_text(element, "./adv:gemarkung/adv:AX_Gemarkung_Schluessel/adv:gemarkungsnummer")
        ),
        "field_number_original": find_text(element, "./adv:flurnummer"),
        "denominator": parse_int(
            find_text(
                element,
                "./adv:flurstuecksnummer/adv:AX_Flurstuecksnummer/adv:nenner",
            )
        ),
        "numerator": parse_int(
            find_text(
                element,
                "./adv:flurstuecksnummer/adv:AX_Flurstuecksnummer/adv:zaehler",
            )
        ),
        "different_legal_status": parse_bool(find_text(element, "./adv:abweichenderRechtszustand")),
        "wkt_geometry": geometry_wkt,
    }

    if data["adv_id"] is None:
        logging.debug("missing ADV identifier for one parcel; skipping")
        return None

    if data["cadastral_district_number"] is None:
        logging.debug("missing cadastral district for parcel %s", data["adv_id"])
        return None

    return data


def insert_parcel(cursor: PsycopgCursor, data: dict[str, t.Any]) -> None:
    sql = SQL(
        """
        INSERT INTO {table} (
            adv_id, start_time, state_number,
            administrative_district_number, county_number, municipality_number,
            cadastral_district_number, field_number_original, denominator, numerator,
            different_legal_status, wkb_geometry
        )
        VALUES (
            %(adv_id)s, %(start_time)s, %(state_number)s,
            %(administrative_district_number)s, %(county_number)s, %(municipality_number)s,
            %(cadastral_district_number)s, %(field_number_original)s, %(denominator)s,
            %(numerator)s, %(different_legal_status)s,
            CASE WHEN %(wkt_geometry)s IS NULL THEN NULL
                 ELSE ST_AsBinary(
                    ST_Multi(
                        ST_Transform(ST_GeomFromText(%(wkt_geometry)s, 25832), 4326)
                    )
                 )
            END
        )
        """
    ).format(table=Identifier("sh_alkis_parcel"))

    cursor.execute(sql, data)


def insert_batch(cursor: PsycopgCursor, rows: list[dict[str, t.Any]]) -> None:
    if not rows:
        return

    sql = SQL(
        """
        INSERT INTO {table} (
            adv_id, start_time, state_number,
            administrative_district_number, county_number, municipality_number,
            cadastral_district_number, field_number_original, denominator, numerator,
            different_legal_status, wkb_geometry
        ) VALUES %s
        """
    ).format(table=Identifier("sh_alkis_parcel"))

    template = (
        "(%(adv_id)s, %(start_time)s, %(state_number)s, %(administrative_district_number)s,"
        " %(county_number)s, %(municipality_number)s, %(cadastral_district_number)s,"
        " %(field_number_original)s, %(denominator)s, %(numerator)s, %(different_legal_status)s,"
        " ST_AsBinary(ST_Multi(ST_Transform(ST_GeomFromText(%(wkt_geometry)s, 25832), 4326))))"
    )

    execute_values(cursor, sql.as_string(cursor), rows, template=template)


def collect_sources(inputs: tuple[Path, ...], recursive: bool) -> list[Path]:
    patterns = ("*.xml", "*.xml.gz", "*.nas", "*.nas.gz")
    files: set[Path] = set()

    for entry in inputs:
        if entry.is_dir():
            iterator = entry.rglob if recursive else entry.glob
            for pattern in patterns:
                for candidate in iterator(pattern):
                    if candidate.is_file():
                        files.add(candidate)
        elif entry.is_file():
            name = entry.name.lower()
            if name.endswith((".xml", ".xml.gz", ".nas", ".nas.gz")):
                files.add(entry)
            else:
                logging.debug("skipping unsupported input file %s", entry)

    ordered = sorted(files)
    logging.debug("collected %s input files", len(ordered))
    return ordered


def process_file(
    path: Path,
    cursor: PsycopgCursor,
    stats: ImportStats,
    commit_interval: int,
    batch_size: int,
    limit: t.Optional[int],
) -> bool:
    stats.files_seen += 1
    logging.info("processing %s", path)

    seen_before = stats.parcels_seen
    inserted_before = stats.parcels_inserted
    skipped_before = stats.parcels_skipped
    errors_before = stats.errors

    batch: list[dict[str, t.Any]] = []

    for parcel in iter_flurstuecke(path):
        if limit is not None and stats.parcels_inserted >= limit:
            if batch:
                flush_batch(cursor, batch, stats, path, commit_interval, limit)
            return False

        stats.parcels_seen += 1

        data = extract_parcel(parcel)

        if not data:
            stats.parcels_skipped += 1
            continue

        batch.append(data)

        if batch_size > 0 and len(batch) >= batch_size:
            if not flush_batch(cursor, batch, stats, path, commit_interval, limit):
                return False

    if batch:
        if not flush_batch(cursor, batch, stats, path, commit_interval, limit):
            return False

    logging.info(
        "finished %s: seen %s, inserted %s, skipped %s, errors %s",
        path,
        stats.parcels_seen - seen_before,
        stats.parcels_inserted - inserted_before,
        stats.parcels_skipped - skipped_before,
        stats.errors - errors_before,
    )

    return True


def flush_batch(
    cursor: PsycopgCursor,
    batch: list[dict[str, t.Any]],
    stats: ImportStats,
    path: Path,
    commit_interval: int,
    limit: t.Optional[int],
) -> bool:
    if not batch:
        return True

    rows = list(batch)
    batch.clear()

    try:
        insert_batch(cursor, rows)
        inserted = len(rows)
    except Exception as error:  # pragma: no cover - database runtime failures
        logging.error(
            "failed to insert batch (%s rows) from %s: %s; falling back to row inserts",
            len(rows),
            path,
            error,
        )
        cursor.connection.rollback()
        inserted = 0

        for row in rows:
            try:
                insert_parcel(cursor, row)
            except Exception as row_error:
                stats.errors += 1
                logging.error(
                    "failed to insert parcel %s: %s",
                    row.get("adv_id"),
                    row_error,
                )
                cursor.connection.rollback()
                continue

            inserted += 1

            if commit_interval > 0 and (stats.parcels_inserted + inserted) % commit_interval == 0:
                cursor.connection.commit()
                logging.info("committed %s parcels", stats.parcels_inserted + inserted)

    stats.parcels_inserted += inserted

    if commit_interval > 0 and stats.parcels_inserted % commit_interval == 0:
        cursor.connection.commit()
        logging.info("committed %s parcels", stats.parcels_inserted)

    if limit is not None and stats.parcels_inserted >= limit:
        return False

    return True


@click.command()
@click.option("--env", "env_path", type=click.Path(exists=True, path_type=Path), required=True, help="Path to .env with database credentials")
@click.option(
    "--input",
    "inputs",
    type=click.Path(exists=True, path_type=Path),
    multiple=True,
    required=True,
    help="NAS/GML file or directory containing ALKIS downloads",
)
@click.option("--recursive/--no-recursive", default=True, show_default=True, help="Recurse into sub-directories when --input points to a folder")
@click.option("--commit-interval", default=500, show_default=True, help="Number of inserts per transaction commit")
@click.option("--batch-size", default=200, show_default=True, help="Number of parcels to bulk insert at once")
@click.option("--limit", type=int, help="Stop after inserting this many parcels")
@click.option("--verbose", "-v", is_flag=True, help="Enable INFO log output")
@click.option("--debug", "-d", is_flag=True, help="Enable DEBUG log output")
def main(env_path: Path, inputs: tuple[Path, ...], recursive: bool, commit_interval: int, batch_size: int, limit: t.Optional[int], verbose: bool, debug: bool) -> None:
    """Insert ALKIS parcel geometries into the sh_alkis_parcel table."""

    configure_logging(verbose, debug)

    try:
        conn: PsycopgConnection = load_env(env_path)
    except Exception as error:
        logging.error("failed to connect to database: %s", error)
        sys.exit(1)

    stats = ImportStats()

    files = collect_sources(inputs, recursive)

    if not files:
        logging.warning("no input files found")
        return

    logging.info("found %s input file(s)", len(files))

    cursor: PsycopgCursor = conn.cursor()

    try:
        for file_path in files:
            if not process_file(file_path, cursor, stats, commit_interval, batch_size, limit):
                logging.info("limit reached (%s parcels)", stats.parcels_inserted)
                break

        conn.commit()
    finally:
        cursor.close()
        conn.close()

    logging.info(
        "processed %s file(s); inserted %s parcel(s); skipped %s; errors %s",
        stats.files_seen,
        stats.parcels_inserted,
        stats.parcels_skipped,
        stats.errors,
    )


if __name__ == "__main__":
    sys.excepthook = log_exceptions
    main()

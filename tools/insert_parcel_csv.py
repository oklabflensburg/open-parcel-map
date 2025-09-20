import os
import sys
import click
import traceback
import logging as log
import psycopg2
import csv

from datetime import datetime
from dotenv import load_dotenv
from pathlib import Path



# log uncaught exceptions
def log_exceptions(type, value, tb):
    for line in traceback.TracebackException(type, value, tb).format(chain=True):
        log.exception(line)

    log.exception(value)

    sys.__excepthook__(type, value, tb) # calls default excepthook


def connect_database(env_path):
    try:
        load_dotenv(dotenv_path=Path(env_path))

        conn = psycopg2.connect(
            database = os.getenv('DB_NAME'),
            password = os.getenv('DB_PASS'),
            user = os.getenv('DB_USER'),
            host = os.getenv('DB_HOST'),
            port = os.getenv('DB_PORT')
        )

        conn.autocommit = True

        log.info('connection to database established')

        return conn
    except Exception as e:
        log.error(e)

        sys.exit(1)


def str_to_bool(v):
    return v.lower() in ('yes', 'true', 't', '1')


def parse_datetime(s):
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ")


def parse_value(value, conversion_func=None):
    if value is None or value == '':
        return None

    if conversion_func:
        return conversion_func(value)

    return value


def insert_row(cur, row):
    adv_id = parse_value(row.get('adv_id'))
    start_time = parse_value(row.get('beginnt'), parse_datetime)
    state_number = parse_value(row.get('land'))
    administrative_district_number = parse_value(row.get('regierungsbezirk'), int)
    county_number = parse_value(row.get('kreis'), int)
    municipality_number = parse_value(row.get('gemeinde'), int)
    cadastral_district_number = parse_value(row.get('gemarkungsnummer'), int)
    field_number_original = parse_value(row.get('flurnummer'))
    denominator = parse_value(row.get('nenner'), int)
    numerator = parse_value(row.get('zaehler'), int)
    different_legal_status = parse_value(row.get('abweichender_rechtszustand'), str_to_bool)
    wkt_geometry = parse_value(row.get('wkt_geometry'))

    if not wkt_geometry:
        log.error(f'skipping {adv_id}: missing geometry')
        return

    sql = '''
        INSERT INTO sh_alkis_parcel (adv_id, start_time, state_number,
            administrative_district_number, county_number, municipality_number,
            cadastral_district_number, field_number_original, denominator, numerator,
            different_legal_status, wkb_geometry)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
            ST_AsBinary(
                ST_Multi(ST_Transform(ST_GeomFromText(%s, 25832), 4326))
            )) RETURNING id
    '''

    try:
        cur.execute(sql, (adv_id, start_time, state_number, administrative_district_number,
            county_number, municipality_number, cadastral_district_number, field_number_original,
            denominator, numerator, different_legal_status, wkt_geometry))

        last_inserted_id = cur.fetchone()[0]

        log.info(f'inserted {adv_id} with id {last_inserted_id}')
    except Exception as e:
        log.error(e)


def read_csv(conn, src):
    cur = conn.cursor()

    with open(src, newline='') as csvfile:
        reader = csv.DictReader(csvfile, delimiter=',')
    
        for row in reader:
            insert_row(cur, row)


@click.command()
@click.option('--env', '-e', type=str, required=True, help='Set your local dot env path')
@click.option('--src', '-s', type=click.Path(exists=True), required=True, help='Set src path to your csv')
@click.option('--verbose', '-v', is_flag=True, help='Print more verbose output')
@click.option('--debug', '-d', is_flag=True, help='Print detailed debug output')
def main(env, src, verbose, debug):
    if debug:
        log.basicConfig(format='%(levelname)s: %(message)s', level=log.DEBUG)
    if verbose:
        log.basicConfig(format='%(levelname)s: %(message)s', level=log.INFO)
        log.info(f'set logging level to verbose')
    else:
        log.basicConfig(format='%(levelname)s: %(message)s')

    recursion_limit = sys.getrecursionlimit()
    log.info(f'your system recursion limit: {recursion_limit}')

    conn = connect_database(env)
    data = read_csv(conn, Path(src))


if __name__ == '__main__':
    sys.excepthook = log_exceptions

    main()

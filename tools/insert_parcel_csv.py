import os
import re
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


def insert_row(cur, row):
    adv_id = row['adv_id']
    beginnt = parse_datetime(row['beginnt']) if row['beginnt'] else None
    land = row['land'] if row['land'] else None
    regierungsbezirk = int(row['regierungsbezirk']) if row['regierungsbezirk'] else None
    kreis = int(row['kreis']) if row['kreis'] else None
    gemeinde = row['gemeinde'] if row['gemeinde'] else None
    gemarkungsnummer = int(row['gemarkungsnummer']) if row['gemarkungsnummer'] else None
    flurnummer = int(row['flurnummer']) if row['flurnummer'] else None
    nenner = int(row['nenner']) if row['nenner'] else None
    zaehler = int(row['zaehler']) if row['zaehler'] else None
    abweichender_rechtszustand = str_to_bool(row['abweichender_rechtszustand']) if row['abweichender_rechtszustand'] else None
    wkt_geometry = row['wkt_geometry']

    # Parse the identifier and the polygon coordinates
    match = re.match(r'Polygon\(\((.*?)\)\)', wkt_geometry)
    coordinates = match.group(1)

    wkt_geometry = f'POLYGON(({coordinates}))'

    sql = '''
        INSERT INTO sh_alkis_parcel (adv_id, beginnt, land, regierungsbezirk, kreis, gemeinde,
            gemarkungsnummer, flurnummer, nenner, zaehler, abweichender_rechtszustand, wkb_geometry)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, ST_AsBinary(ST_Transform(ST_GeomFromText(%s, 25832), 4326))) RETURNING id
    '''

    try:
        cur.execute(sql, (adv_id, beginnt, land, regierungsbezirk, kreis, gemeinde,
            gemarkungsnummer, flurnummer, nenner, zaehler, abweichender_rechtszustand, wkt_geometry))

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

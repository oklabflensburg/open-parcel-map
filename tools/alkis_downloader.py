import os
import sys
import time
import click
import httpx
import traceback
import logging as log
import magic

from httpx import ReadTimeout
from fake_useragent import UserAgent
from pathlib import Path



# log uncaught exceptions
def log_exceptions(type, value, tb):
    for line in traceback.TracebackException(type, value, tb).format(chain=True):
        log.exception(line)

    log.exception(value)

    sys.__excepthook__(type, value, tb) # calls default excepthook


def save_download(download_path, data):
    directories = Path(download_path).parent.resolve()
    Path(directories).mkdir(parents=True, exist_ok=True)

    try:
        with open(download_path, 'wb') as f:
            f.write(data)
    except PermissionError as e:
        log.error(e)

    log.info(f'saved archieve to {download_path}')


def get_mime_type(download_path):
    mime_type = magic.from_file(download_path, mime=True)

    return mime_type


def rename_download(download_path, archive_path):
    os.rename(download_path, archive_path)


def download_archive(url):
    try:
        r = httpx.get(url, verify=False)
    except ReadTimeout as e:
        time.sleep(5)
        r = download_archive(url)

    if r.status_code == httpx.codes.OK:
        return r.content

    return None


def status_request(job_id, tile_id, tile_gemarkung, tile_flur, user_agent):
    time_stamp = int(time.time())
    headers = {'Content-Type': 'application/json', 'User-Agent': user_agent}
    url = f'https://geodaten.schleswig-holstein.de/gaialight-sh/_apps/dladownload/multi.php?action=status&job={job_id}&_={time_stamp}'
    data = None

    r = httpx.get(url, headers=headers, verify=False)

    if r.status_code != httpx.codes.OK:
        log.error(f'request failed with status {r.status_code}')

        return

    data = r.json()

    try:
        while data is not None and data['status'] != 'done':
            time.sleep(1)
            data = status_request(job_id, tile_id, tile_gemarkung, tile_flur, user_agent)
    except Exception as e:
        log.error(f'{e} bei tile_id: {tile_id} in der Gemarkung: {tile_gemarkung} und Flurstück: {tile_flur}')

        return

    if data is not None and data['success'] is False:
        msg = reponse_status['msg']
        log.error(f'{msg} bei tile_id: {tile_id} in der Gemarkung: {tile_gemarkung} und Flurstück: {tile_flur}')

        return

    return data


def job_request(tile_id, tile_flur, user_agent):
    time_stamp = int(time.time())
    headers = {'Content-Type': 'application/json', 'User-Agent': user_agent}
    url = f'https://geodaten.schleswig-holstein.de/gaialight-sh/_apps/dladownload/multi.php?url={tile_flur}.xml.gz&buttonClass=file1&id={tile_id}&type=alkis&action=start&_={time_stamp}'

    r = httpx.get(url, headers=headers, verify=False)

    if r.status_code == httpx.codes.OK:
        return r.json()

    return {}


def tile_request(tile_id, user_agent):
    headers = {'Content-Type': 'application/json', 'User-Agent': user_agent}
    url = f'https://geodaten.schleswig-holstein.de/gaialight-sh/_apps/dladownload/_ajax/details.php?type=alkis&id={tile_id}'

    r = httpx.get(url, headers=headers, verify=False)

    if r.status_code == httpx.codes.OK:
        return r.json()

    return {}


def fetch_data(tile_id, path, verbose):
    ua = UserAgent()
    user_agent = ua.random

    response_tile = tile_request(tile_id, user_agent)

    if response_tile['success'] is False:
        log.error(response_tile['message'])

        return
    else:
        log.info(response_tile)

    tile_flur = response_tile['object']['flur']
    tile_gemarkung = response_tile['object']['gemarkung']

    response_job = job_request(tile_id, tile_flur, user_agent)
    log.info(response_job)

    if response_job['success'] is False:
        msg = response_job['message']
        log.error(f'{msg} mit der {tile_id} mit der Gemarkung {tile_gemarkung} und Flustück {tile_flur}')

        return

    while response_job['success'] is not True:
        time.sleep(1)
        response_job = job_request(tile_id, tile_flur, user_agent)
        log.info(response_job)

    job_id = response_job['id']

    reponse_status = status_request(job_id, tile_id, tile_gemarkung, tile_flur, user_agent)
    log.info(reponse_status)

    try:
        data = download_archive(reponse_status['downloadUrl'])

        file_name = f'{tile_id}_{tile_flur}'

        if path is not None and Path(path).is_dir():
            download_path = Path(f'{path}/sh/alkis/{file_name}.zip').resolve()
        else:
            download_path = Path(f'../data/sh/alkis/{file_name}.zip').resolve()

        save_download(download_path, data)
    except Exception as e:
        log.error(f'{e} bei tile_id: {tile_id} in der Gemarkung: {tile_gemarkung} und Flurstück: {tile_flur}')

        return


@click.command()
@click.option('--debug', '-d', is_flag=True, help='Print more debug output')
@click.option('--verbose', '-v', is_flag=True, help='Print more verbose output')
@click.option('--path', '-p', type=str, help='Set the source output format')
@click.argument('start', type=int, nargs=1)
@click.argument('end', type=int, nargs=1)
def main(start, end, path, verbose, debug):
    if debug:
        log.basicConfig(format='%(levelname)s: %(message)s', level=log.DEBUG)
    if verbose:
        log.basicConfig(format='%(levelname)s: %(message)s', level=log.INFO)
    else:
        log.basicConfig(format='%(levelname)s: %(message)s')

    if not start <= end:
        log.error('argument start must be greater as end')
        sys.exit(1)

    for tile_id in range(start, end):
        fetch_data(tile_id, path, verbose)


if __name__ == '__main__':
    print(sys.getrecursionlimit())
    sys.excepthook = log_exceptions
    main()

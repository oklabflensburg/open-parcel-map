#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import sys
import time
import traceback
import logging as log

from pathlib import Path
from typing import Iterable, List, Optional
from urllib.parse import parse_qs, urlparse

import click
import httpx
from fake_useragent import UserAgent


DEFAULT_OUTPUT_DIR = Path('../data/sh/alkis')
USER_AGENT_FALLBACK = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'


# log uncaught exceptions
def log_exceptions(exc_type, value, tb):
    for line in traceback.TracebackException(exc_type, value, tb).format(chain=True):
        log.exception(line)

    log.exception(value)

    sys.__excepthook__(exc_type, value, tb)


def resolve_output_dir(path: Optional[Path]) -> Path:
    if path and path.is_dir():
        return path.resolve()

    if path and not path.exists():
        return path.resolve()

    return DEFAULT_OUTPUT_DIR.resolve()


def ensure_directory(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def save_download(download_path: Path, data: bytes) -> None:
    ensure_directory(download_path)

    try:
        with open(download_path, 'wb') as file_handle:
            file_handle.write(data)
    except PermissionError as error:
        log.error(error)
        return

    log.info('saved archive to %s', download_path)


def get_user_agent() -> str:
    try:
        return UserAgent().random
    except Exception as error:  # pragma: no cover - network/database errors from fake_useragent
        log.debug('failed to create random user agent, using fallback: %s', error)
        return USER_AGENT_FALLBACK


def load_geojson(source: str) -> dict:
    if source.startswith(('http://', 'https://')):
        with httpx.Client(verify=False, timeout=30.0) as client:
            response = client.get(source)
            response.raise_for_status()
            return response.json()

    path = Path(source).expanduser().resolve()

    with open(path, 'r', encoding='utf-8') as file_handle:
        return json.load(file_handle)


def extract_features(geojson: dict) -> List[dict]:
    if geojson.get('type') != 'FeatureCollection':
        raise ValueError('GeoJSON must be a FeatureCollection')

    features = geojson.get('features')

    if not isinstance(features, list):
        raise ValueError('GeoJSON FeatureCollection is missing a features array')

    return features


def slice_features(features: List[dict], start: int, end: Optional[int]) -> Iterable[dict]:
    if start < 0:
        raise ValueError('start_index cannot be negative')

    if end is not None and end < start:
        raise ValueError('end_index must be greater than or equal to start_index')

    return features[start:end]


def derive_filename(properties: dict, link: Optional[str]) -> str:
    if link:
        parsed = urlparse(link)
        query_file = parse_qs(parsed.query).get('file')

        if query_file and query_file[0]:
            return query_file[0]

        link_name = Path(parsed.path).name

        if link_name:
            return link_name

    flur = properties.get('flur')
    if flur:
        return f'{flur}.xml.gz'

    gemarkung = properties.get('gemarkung')
    if gemarkung:
        return f'{gemarkung}.xml.gz'

    schlgmd = properties.get('schlgmd')
    if schlgmd:
        return f'{schlgmd}.xml.gz'

    return 'download.xml.gz'


def build_download_path(properties: dict, output_dir: Path, link: Optional[str]) -> Path:
    quartal = properties.get('quartal')
    filename = derive_filename(properties, link)

    if quartal:
        return output_dir / quartal / filename

    return output_dir / filename


def download_archive(url: str, client: httpx.Client, user_agent: str, retries: int = 3, backoff: float = 2.0) -> bytes:
    headers = {'User-Agent': user_agent}
    last_error: Optional[Exception] = None

    for attempt in range(1, retries + 1):
        try:
            response = client.get(url, headers=headers)
            response.raise_for_status()
            return response.content
        except (httpx.HTTPStatusError, httpx.RequestError) as error:
            last_error = error
            log.warning('attempt %s/%s failed for %s: %s', attempt, retries, url, error)

            if attempt < retries:
                time.sleep(backoff * attempt)

    raise RuntimeError(f'failed to download {url}') from last_error


@click.command()
@click.option('--debug', '-d', is_flag=True, help='Print debug output')
@click.option('--verbose', '-v', is_flag=True, help='Print more verbose output')
@click.option('--output', '-o', 'output_path', type=click.Path(file_okay=False, resolve_path=True, path_type=Path), help='Target directory for downloads')
@click.option('--geojson', '-g', 'geojson_source', required=True, type=str, help='Path or URL to the GeoJSON index')
@click.option('--start-index', '-s', default=0, show_default=True, type=int, help='Start index (inclusive) within the GeoJSON features array')
@click.option('--end-index', '-e', default=None, type=int, help='End index (exclusive) within the GeoJSON features array')
@click.option('--dry-run', is_flag=True, help='Only print which files would be downloaded')
@click.option('--skip-existing/--force', default=True, show_default=True, help='Skip downloads if the target file already exists')
@click.option('--timeout', default=30.0, show_default=True, type=float, help='HTTP timeout in seconds')
def main(geojson_source: str, output_path: Optional[Path], verbose: bool, debug: bool, start_index: int, end_index: Optional[int], dry_run: bool, skip_existing: bool, timeout: float):
    if debug:
        log.basicConfig(format='%(levelname)s: %(message)s', level=log.DEBUG)
    elif verbose:
        log.basicConfig(format='%(levelname)s: %(message)s', level=log.INFO)
    else:
        log.basicConfig(format='%(levelname)s: %(message)s')

    try:
        geojson = load_geojson(geojson_source)
        features = extract_features(geojson)
        selected_features = list(slice_features(features, start_index, end_index))
    except Exception as error:
        log.error('failed to prepare feature list: %s', error)
        sys.exit(1)

    if not selected_features:
        log.info('no features selected for download')
        return

    output_dir = resolve_output_dir(output_path)
    user_agent = get_user_agent()

    log.info('downloading %s feature(s) to %s', len(selected_features), output_dir)

    with httpx.Client(verify=False, timeout=timeout) as client:
        for index, feature in enumerate(selected_features, start=start_index):
            properties = feature.get('properties', {})
            link = properties.get('link_data')

            if not link:
                log.warning('feature #%s has no link_data property; skipping', index)
                continue

            download_path = build_download_path(properties, output_dir, link)

            if skip_existing and download_path.exists():
                log.info('skipping existing file %s', download_path)
                continue

            if dry_run:
                log.info('dry run: would download %s to %s', link, download_path)
                continue

            try:
                data = download_archive(link, client, user_agent)
            except Exception as error:
                log.error('failed to download %s: %s', link, error)
                continue

            save_download(download_path, data)


if __name__ == '__main__':
    sys.excepthook = log_exceptions
    main()

# ALKIS Downloader

This script automates downloading Schleswig-Holstein ALKIS parcel archives listed in a GeoJSON index. It reads each feature's `link_data` URL, organises the downloads into folders (by `quartal` when available), and skips files you've already retrieved unless you explicitly force a re-download.

## Prerequisites

- Python 3.10 or newer (the project targets modern Python in the rest of the tooling).
- The `tools/requirements.txt` dependencies installed, ideally inside a virtual environment:

  ```bash
  cd tools
  python -m venv .venv
  source .venv/bin/activate
  pip install -r requirements.txt
  ```

  The most relevant packages are `click`, `httpx`, and `fake-useragent`. The script falls back to a static browser user-agent if the local user-agent cache cannot be built.


## Data sources

- Download overview page: https://geodaten.schleswig-holstein.de/gaialight-sh/_apps/dladownload/dl-alkis.html
- Direct GeoJSON index: https://geodaten.schleswig-holstein.de/gaialight-sh/_apps/dladownload/single.php?file=ALKIS_SH_Massendownload.geojson&id=4

## Running the downloader

The script lives in `tools/alkis_downloader.py` and exposes a Click-based CLI. The minimum input is a path or URL to the GeoJSON index:

```bash
python tools/alkis_downloader.py --geojson tools/single.php?file=ALKIS_SH_Massendownload.geojson&id=4
```

All downloads will be written beneath `../data/sh/alkis` relative to the script unless you choose another directory.

### CLI options

| Option                           | Description                                                                                                    |
| -------------------------------- | -------------------------------------------------------------------------------------------------------------- |
| `-g`, `--geojson`                | Path or URL to the GeoJSON FeatureCollection (required).                                                       |
| `-o`, `--output`                 | Target directory for downloads. Defaults to `../data/sh/alkis`. Missing directories are created automatically. |
| `-s`, `--start-index`            | Inclusive start index within the GeoJSON features array. Default: `0`.                                         |
| `-e`, `--end-index`              | Exclusive end index within the features array. Leave unset to process to the end.                              |
| `--dry-run`                      | Print which files would be downloaded without making network requests.                                         |
| `--no-skip-existing` / `--force` | Force a re-download even if the output file already exists. By default, existing files are skipped.            |
| `--timeout`                      | HTTP timeout in seconds (default `30.0`).                                                                      |
| `-v`, `--verbose`                | Increase logging to INFO.                                                                                      |
| `-d`, `--debug`                  | Enable DEBUG-level logging for troubleshooting.                                                                |

### Typical workflows

Dry-run the full list to confirm selection and filenames:

```bash
python tools/alkis_downloader.py \
  --geojson tools/single.php?file=ALKIS_SH_Massendownload.geojson&id=4 \
  --dry-run
```

Download the first 50 features into a custom directory:

```bash
python tools/alkis_downloader.py \
  --geojson tools/single.php?file=ALKIS_SH_Massendownload.geojson&id=4 \
  --output /tmp/alkis \
  --start-index 0 \
  --end-index 50
```

Re-download every archive, regardless of whether an existing file is present:

```bash
python tools/alkis_downloader.py --geojson <geojson> --force
```

### Output layout

- Files are named using the `link_data` query string (`file=...`), falling back to `flur`, `gemarkung`, or `schlgmd` properties when necessary.
- When a `quartal` property exists, the archive is placed under `<output>/<quartal>/`. Otherwise, it is written directly inside the chosen output directory.

### Error handling & retries

- The script retries downloads up to three times with a short backoff. Failures are logged and the script moves on to the next feature.
- Missing `link_data` values are skipped with a warning.
- Any unhandled exception is logged via the custom exception hook before the process exits.

## Tips

- Use `--dry-run` on large GeoJSON files to confirm that your `start-index` and `end-index` arguments select the intended features.
- Pair the downloader with a cron job or CI task by pointing to a remote GeoJSON URL (authentication is not handled).
- For reproducibility, pin your dependencies with `tools/requirements.txt` and keep the virtual environment isolated.

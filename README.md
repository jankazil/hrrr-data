# HRRR-data

**HRRR-data** is a Python toolkit for accessing, downloading, and processing High-Resolution Rapid Refresh (HRRR) forecast data from NOAA’s public S3 bucket. It provides utilities for listing available files, downloading data in GRIB2 format, converting GRIB2 to netCDF, and extracting selected variables from netCDF files.

## Installation (Linux / macOS)

```bash
pip install git+https://github.com/jankazil/hrrr-data
```

## Usage

This repository provides two top-level scripts for working with HRRR surface forecast data:

- **`DownloadHRRRSurfaceForecast.py`**  

  Downloads HRRR surface forecast GRIB2 files from NOAA’s public S3 bucket for a specified date range, forecast initialization hour, valid hour, and region. Call with -h to obtain detailed usage information.  

  The script:
  1. Accepts user-specified start and end dates, initialization hour, forecast valid hour, region, and local output directory.
  2. Downloads the matching GRIB2 files.
  3. Converts each GRIB2 file to netCDF containing commonly used subset of variables (temperature, dew point, relative humidity, wind components, precipitation) and writes them to netCDF files with metadata.

- **`ConvertHRRRSurfaceForecast2netCDF.py`**  

  Processes a single local HRRR GRIB2 file and writes a new netCDF file containing a selected set of variables. Call with -h to obtain detailed usage information.  

  The script:
  1. Accepts the path to a GRIB2 file as input.
  2. Extracts a predefined set of meteorological variables, including temperature, dew point, humidity, wind, and precipitation.
  3. Writes the selected variables and metadata to a netCDF file and removes the intermediate netCDF file created during conversion.

The GRIB-to-netCDF conversion requires `ncl_convert2nc` to be installed and available on the system path.

## Modules

- **`s3.py`**: Functions for interacting with the NOAA HRRR S3 bucket, including:
  - Listing available files via direct path matching or wildcard-style expressions
  - Downloading HRRR data files from S3 to a local directory
  - Retrieving S3 object metadata (size, last modified, ETag, user-defined metadata, etc.) for a file within the NOAA HRRR S3 bucket

- **`tools.py`**: Utilities for working with HRRR data in GRIB2 and netCDF formats, including:
  - Listing variables in GRIB2 files (`pygrib`)
  - Converting GRIB2 files to netCDF using `ncl_convert2nc`
  - Extracting selected variables from netCDF files using `xarray`
  - Retrieving the metadata for a HRRR file in S3

- **`plotting`**: Utilities for plotting HRRR data.

## Demo Scripts

The `demos` directory provides example scripts demonstrating individual operations:

- `demo_s3_ls.py` and `demo_s3_ls_re.py` — List available HRRR files in the NOAA S3 bucket.
- `demo_s3_download.py` — Download a single GRIB2 file.
- `demo_s3_download_date_range.py` — Download GRIB2 files for a given date range.
- `demo_tools_grib_list_vars.py` — List variables in a GRIB2 file.
- `demo_tools_grib2nc.py` — Convert a GRIB2 file to netCDF.
- `demo_tools_nc2nc_extract_vars.py` — Extract a subset of variables from an existing netCDF file.
- `demo_s3_info.py` — Retrieve and display S3 object metadata.

## Development

### Code Quality and Testing Commands

- `make fmt` - Runs ruff format, which automatically reformats Python files according to the style rules in `pyproject.toml`
- `make lint` - Runs ruff check --fix, which lints the code (checks for style errors, bugs, outdated patterns, etc.) and auto-fixes what it can.
- `make check` - Runs fmt and lint.
- `make type` - Runs mypy, the static type checker, using the strictness settings from `pyproject.toml`. Mypy is a static type checker for Python, a dynamically typed language. Because static analysis cannot account for all dynamic runtime behaviors, mypy may report false positives which do no reflect actual runtime issues. The usefulness of mypy is therefore limited, unless the developer compensates with extra work for the choices that were made when Python was originally designed.
- `make test` - Runs pytest with coverage reporting (configured in `pyproject.toml`).

## Disclaimer

The HRRR data accessed by this software are publicly available from NOAA and are subject to their terms of use. This project is not affiliated with or endorsed by NOAA.

## Author
Jan Kazil - jan.kazil.dev@gmail.com - [jankazil.com](https://jankazil.com)  

## License

BSD 3-clause


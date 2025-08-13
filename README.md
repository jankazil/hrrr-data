# HRRR-data

**HRRR-data** is a Python toolkit for accessing, downloading, and processing High-Resolution Rapid Refresh (HRRR) forecast data from NOAA’s public S3 bucket. It provides utilities for listing available files, downloading data in GRIB2 format, converting GRIB2 to netCDF, and extracting selected variables from netCDF files.

## Overview

The project consists of the following modules:

- **`s3.py`**: Functions for interacting with the NOAA HRRR S3 bucket, including:
  - Listing available files via direct path matching or wildcard-style expressions
  - Downloading HRRR data files from S3 to a local directory
  - Retrieving S3 object metadata (size, last modified, ETag, user-defined metadata, etc.) for a file within the NOAA HRRR S3 bucket

- **`tools.py`**: Utilities for working with HRRR data in GRIB2 and netCDF formats, including:
  - Listing variables in GRIB2 files (`pygrib`)
  - Converting GRIB2 files to netCDF using `ncl_convert2nc`
  - Extracting selected variables from netCDF files using `xarray`
  - Retrieving the metadata for a HRRR file in S3

## Usage

Demo scripts demonstrate usage and serve as functional examples. See the `demos` directory:

- `demo_s3_ls.py` and `demo_s3_ls_re.py` for listing available HRRR files
- `demo_s3_download.py` for downloading a sample GRIB2 file
- `demo_s3_download_date_range.py` for downloading a GRIB2 files for a given date range
- `demo_tools_grib_list_vars.py` for variable introspection
- `demo_tools_grib2nc.py` for file format conversion
- `demo_tools_nc2nc_extract_vars.py` for variable filtering
- `demo_s3_info.py` for retrieving and displaying object metadata for a file in the NOAA HRRR S3 bucket

## Development

### Code Quality and Testing Commands

- `make fmt` - Runs ruff format, which automatically reformats Python files according to the style rules in `pyproject.toml`
- `make lint` - Runs ruff check --fix, which lints the code (checks for style errors, bugs, outdated patterns, etc.) and auto-fixes what it can.
- `make check` - Runs fmt and lint.
- `make type` - Runs mypy, the static type checker, using the strictness settings from `pyproject.toml`. Mypy is a static type checker for Python, a dynamically typed language. Because static analysis cannot account for all dynamic runtime behaviors, mypy may report false positives which do no reflect actual runtime issues. The usefulness of mypy is therefore limited, unless the developer compensates with extra work for the choices that were made when Python was originally designed.
- `make test` - Runs pytest with coverage reporting (configured in `pyproject.toml`).

## Notes

- The S3 operations are read-only and anonymous; no credentials are required.
- The GRIB-to-netCDF conversion requires `ncl_convert2nc` to be installed and available on the system path.

## Disclaimer

The HRRR data accessed by this software are publicly available from NOAA and are subject to their terms of use. This project is not affiliated with or endorsed by NOAA.

## Author
Jan Kazil - jan.kazil.dev@gmail.com - [jankazil.com](https://jankazil.com)  

## License

BSD 3-clause


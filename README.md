# HRRR-data

**HRRR-data** is a Python toolkit for accessing, downloading, and processing High-Resolution Rapid Refresh (HRRR) forecast data from NOAA’s public S3 bucket.

It provides:

- Top level command-line tools that
  - Download HRRR surface forecast GRIB2 files from NOAA’s public S3 bucket for a specified date range, forecast initialization hour, forecast valid hour, and region.
  - Extract a subset of commonly used surface variables from the GRIB2 files into netCDF files.

- Modules for
  - Interacting with the NOAA HRRR S3 bucket and downloading HRRR forecast data
  - Working with HRRR data in GRIB2 and netCDF formats
  - Plotting HRRR data

## Installation (Linux / macOS)

```bash
pip install git+https://github.com/jankazil/hrrr-data
```

## Overview

This repository provides two top-level CLI scripts for working with HRRR surface forecasts:

- **`hrrr-fetch-sfc-forecast`**: Download HRRR surface forecast GRIB2 files for a given date range, initialization hour, valid hour, and region from the NOAA S3 bucket. If requested, a subset of commonly used surface variables (temperature, humidity, wind, precipitation) is extracted into a netCDF file. Both the GRIB2 and the processed netCDF files are stored locally.

- **`hrrr-extract-sfc-vars`**: Process a single local HRRR GRIB2 file (previously downloaded) by converting it to netCDF and writing a new netCDF file that contains only a selected set of variables, with added long names and metadata attributes.

Selected surface variables saved in netCDF files:

  - Air temperature at 2 m above ground
  - Dew point temperature at 2 m above ground
  - Relative humidity at 2 m above ground
  - West-east wind speed at 10 m and 80 m above ground
  - South-north wind speed at 10 m and 80 m above ground
  - 1 h accumulated precipitation
  - Specified height level above ground

## Workflow

The typical workflow is:

1. **Download forecast data** using `hrrr-fetch-sfc-forecast`, specifying the date range, initialization hour, valid hour, and region of interest. This fetches the GRIB2 files from the NOAA HRRR S3 bucket, stores them locally, and, if requested, extracts a selected surface variables into netCDF files.

2. **Extract from a single GRIB2 file** using `hrrr-extract-sfc-vars` when you already have a GRIB2 file available locally and only want to extract a selected set of variables for analysis.

3. **Work with the outputs** in standard netCDF format using your preferred scientific Python libraries (`xarray`, `netCDF4`, etc.), or integrate them into downstream machine learning and analytics workflows.

**Note:** For the conversion from GRIB2 to netCDF, the tool `ncl_convert2nc` needs to be available in the system PATH.

## Command-line interface (CLI)

### `hrrr-fetch-sfc-forecast`

Download HRRR surface forecast GRIB2 files, convert them to netCDF, and extract selected variables.

**Usage:**

```bash
hrrr-fetch-sfc-forecast START_YEAR START_MONTH START_DAY END_YEAR END_MONTH END_DAY INIT_HOUR VALID_HOUR REGION DATA_DIR [-n N_JOBS] [-e]
```

**Arguments:**

- `START_YEAR START_MONTH START_DAY`: beginning of date range (UTC).
- `END_YEAR END_MONTH END_DAY`: end of date range (UTC).
- `INIT_HOUR`: forecast initialization hour.
- `VALID_HOUR`: forecast valid hour.
- `REGION`: HRRR region (e.g. `conus`).
- `DATA_DIR`: local directory for downloads and outputs.
- `-n N_JOBS`: optional, number of parallel downloads.
- `-e`: optional, extract a subset of commonly used surface variables (temperature, humidity, wind, precipitation) into a netCDF file

### `hrrr-extract-sfc-vars`

Extract selected variables from a single local HRRR GRIB2 file into a new netCDF file.

**Usage:**

```bash
hrrr-extract-sfc-vars /path/to/file.grib2
```

**Arguments:**
- `file.grib2`: path to a local HRRR GRIB2 file.

The tool produces a new netCDF file named `<original_basename>_select_vars.nc` with variables such as 2-m air temperature, 2-m dew point, relative humidity, wind components, and 1-hour accumulated precipitation, and adds global metadata identifying the processing.

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

- `demo_s3_ls.py` and `demo_s3_ls_re.py`: List available HRRR files in the NOAA S3 bucket.
- `demo_s3_download.py`: Download a single GRIB2 file.
- `demo_s3_download_date_range.py`: Download GRIB2 files for a given date range.
- `demo_tools_grib_list_vars.py`: List variables in a GRIB2 file.
- `demo_tools_grib2nc.py`: Convert a GRIB2 file to netCDF.
- `demo_tools_nc2nc_extract_vars.py`: Extract a subset of variables from an existing netCDF file.
- `demo_s3_info.py`: Retrieve and display S3 object metadata.

## Development

### Code Quality and Testing Commands

- `make fmt` - Runs ruff format, which automatically reformats Python files according to the style rules in `pyproject.toml`
- `make lint` - Runs ruff check --fix, which checks for style errors, bugs, outdated patterns, etc., and auto-fixes what it can.
- `make check` - Runs fmt and lint.
- `make type` - Currently disabled. Runs mypy, the static type checker, using the strictness settings from `pyproject.toml`.
- `make test` - Runs pytest with reporting (configured in `pyproject.toml`).

## Disclaimer

The HRRR data accessed by this software are publicly available from NOAA and are subject to their terms of use. This project is not affiliated with or endorsed by NOAA.

## Author
Jan Kazil - jan.kazil.dev@gmail.com - [jankazil.com](https://jankazil.com)  

## License

BSD 3-clause

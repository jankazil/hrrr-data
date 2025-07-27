# HRRR-data

**HRRR-data** is a Python toolkit for accessing, downloading, and processing High-Resolution Rapid Refresh (HRRR) forecast data from NOAA’s public S3 bucket. It provides utilities for listing available files, downloading data in GRIB2 format, converting GRIB2 to netCDF, and extracting selected variables from netCDF files.

## Overview

The project consists of two main modules:

- **`s3.py`**: Functions for interacting with the NOAA HRRR S3 bucket, including:
  - Listing available files via direct path matching or wildcard-style expressions
  - Downloading HRRR data files from S3 to a local directory

- **`tools.py`**: Utilities for working with HRRR data in GRIB2 and netCDF formats, including:
  - Listing variables in GRIB2 files (`pygrib`)
  - Converting GRIB2 files to netCDF using `ncl_convert2nc`
  - Extracting selected variables from netCDF files using `xarray`

## Dependencies

- Python ≥ 3.10
- Required Python packages:
  - `s3fs`
  - `pygrib`
  - `xarray`
- Required external tool:
  - `ncl_convert2nc` (part of the NCAR Command Language)

## Usage

All test scripts demonstrate usage and serve as functional examples. See:

- `test_s3_ls.py` and `test_s3_ls_re.py` for listing available HRRR files
- `test_s3_download.py` for downloading a sample GRIB2 file
- `test_s3_download_date_range.py` for downloading a GRIB2 files for a given date range
- `test_tools_grib_list_vars.py` for variable introspection
- `test_tools_grib2nc.py` for file format conversion
- `test_tools_nc2nc_extract_vars.py` for variable filtering

## Notes

- The S3 operations are read-only and anonymous; no credentials are required.
- The GRIB-to-netCDF conversion requires `ncl_convert2nc` to be installed and available on the system path.

## Disclaimer

The HRRR data accessed by this software are publicly available from NOAA and are subject to their terms of use. This project is not affiliated with or endorsed by NOAA.

## Author

Jan Kazil  
[jankazil.com](https://jankazil.com)  
jan.kazil.research@gmail.com

## License

BSD 3-clause


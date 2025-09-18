#!/usr/bin/env python

'''
Download HRRR surface forecast data from the NOAA S3 bucket for a specified date range,
filter by forecast initialization and valid hour, and extract selected variables
into netCDF files.

The script performs the following steps:
1. Parses user-specified start and end dates, forecast initialization hour,
   forecast valid hour, region, and local output directory.
2. Downloads HRRR GRIB2 files from the public S3 bucket for the requested
   time range and parameters, in parallel, with a user-specified number of
   concurrent downloads.
3. Converts downloaded GRIB2 files to netCDF format.
4. Extracts a subset of commonly used variables (e.g., temperature, wind,
   humidity, precipitation) and writes them to separate netCDF files with
   descriptive metadata.

References:
- HRRR documentation: https://rapidrefresh.noaa.gov/hrrr/
- NOAA AWS S3 bucket: https://registry.opendata.aws/noaa-hrrr-pds/
'''

import argparse
import sys
from datetime import datetime
from pathlib import Path

from hrrr_data import s3, tools


def arg_parse(argv=None):
    '''
    Argument parser which returns the parsed values given as arguments.
    '''

    code_description = (
        'Download HRRR surface forecast data from the NOAA S3 bucket for a specified'
        'date range, for a specified forecast initialization and valid hour, and region,'
        'extract select variables into netCDF files, and save the original GRIB2 files'
        'and the processed netCDF files in a local directory.'
    )
    parser = argparse.ArgumentParser(description=code_description)

    # Mandatory arguments
    parser.add_argument('start_year', type=int, help='Start year of time range.')
    parser.add_argument('start_month', type=int, help='Start month of time range.')
    parser.add_argument('start_day', type=int, help='Start day of time range.')
    parser.add_argument('end_year', type=int, help='End year of time range.')
    parser.add_argument('end_month', type=int, help='End month of time range.')
    parser.add_argument('end_day', type=int, help='End day of time range.')
    parser.add_argument(
        'forecast_init_hour',
        type=int,
        help='Forecast initialization hour (not all values may be available, check HRRR documentation).',
    )
    parser.add_argument(
        'forecast_valid_hour',
        type=int,
        help='Forecast valid hour (not all values may be available, check HRRR documentation).',
    )
    parser.add_argument(
        'region',
        type=str,
        help='Region (conus, ...) (not all values may be available, check HRRR documentation).',
    )
    parser.add_argument(
        'data_dir',
        type=str,
        help='Directory path into which the data will be downloaded. Will be created if it does not exist.',
    )

    # Optional arguments
    parser.add_argument('-n','--n', type=int, help='Number of parallel download processes.')

    args = parser.parse_args()

    start_date = datetime(year=args.start_year, month=args.start_month, day=args.start_day)
    end_date = datetime(year=args.end_year, month=args.end_month, day=args.end_day)
    init_hour = args.forecast_init_hour
    forecast_hour = args.forecast_valid_hour
    region = args.region
    local_dir = Path(args.data_dir)
    n_jobs = args.n
    
    return (start_date, end_date, init_hour, forecast_hour, region, local_dir,n_jobs)

(start_date, end_date, init_hour, forecast_hour, region, local_dir, n_jobs) = arg_parse(sys.argv[1:])

#
# Download data
#

data_type = 'wrfsfc'  # Surface data

grib_files = s3.download_date_range(
    start_date, end_date, region, init_hour, forecast_hour, data_type, local_dir, n_jobs = n_jobs
)

#
# Convert to netCDF and extract select variables
#

variables = [
    'TMP_P0_L103_GLC0',
    'DPT_P0_L103_GLC0',
    'RH_P0_L103_GLC0',
    'UGRD_P0_L103_GLC0',
    'VGRD_P0_L103_GLC0',
    'APCP_P8_L1_GLC0_acc1h',
]

long_names = [
    'Air temperature at 2 m above ground',
    'Dew point temperature at 2 m above ground',
    'Relative humidity at 2 m above ground',
    'West-east wind speed',
    'South-north wind speed',
    '1 h accumulated precipitation',
]

global_attributes = {}

global_attributes['model'] = 'HRRR'
global_attributes['processed_with'] = 'https://github.com/jankazil/hrrr-data'

for grib_file in grib_files:
    ncfile = tools.grib2nc(grib_file)
    ncfile_select_vars_name = str(ncfile.stem) + '_select_vars.nc'
    ncfile_select_vars = ncfile.parent / ncfile_select_vars_name
    tools.nc2nc_extract_vars(
        ncfile,
        ncfile_select_vars,
        variables,
        long_names=long_names,
        global_attributes=global_attributes,
    )
    ncfile.unlink()
    print(
        'Extracted select variables from ' + str(grib_file) + ' to ' + str(ncfile_select_vars),
        flush=True,
    )

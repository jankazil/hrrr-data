#!/usr/bin/env python

'''
Extract selected meteorological variables from a local HRRR GRIB2 file
and save them into a new netCDF file.

This script:
1. Accepts a single GRIB2 file path as input.
2. Extracts a predefined set of commonly used variables, including:
   - Air temperature and dew point temperature at 2 m above ground
   - Relative humidity at 2 m above ground
   - Wind components (u and v)
   - 1-hour accumulated precipitation
3. Writes the extracted variables and associated metadata to a new netCDF file,
   and removes the intermediate netCDF file created during conversion.

References:
- HRRR documentation: https://rapidrefresh.noaa.gov/hrrr/
'''

import argparse
import sys
from pathlib import Path

from hrrr_data import tools


def arg_parse(argv=None):
    '''
    Argument parser which returns the parsed values given as arguments.
    '''

    code_description = (
        'Extract from a local HRRR GRIB2 a predefined set of variables (temperature,'
        'humidity, wind, precipitation) and save them in a new netCDF file.'
    )
    parser = argparse.ArgumentParser(description=code_description)

    # Mandatory arguments
    parser.add_argument(
        'grib_file',
        type=str,
        help='Path to GRIB file from which a netCDF file with select variables will be constructed.',
    )

    # Optional arguments
    # parser.add_argument('-x','--xxx', type=str, help='HELP STRING HERE')

    args = parser.parse_args()

    grib_file = Path(args.grib_file)

    return grib_file


grib_file = arg_parse(sys.argv[1:])

#
# Extract select variables and save to netCDF
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

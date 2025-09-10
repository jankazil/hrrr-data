#!/usr/bin/env python
# coding: utf-8

"""
Download files within a given time range from the S3 HRRR bucket,
and extracts select variables into netCDF files.
"""

from datetime import datetime
from pathlib import Path

from hrrr_data import s3
from hrrr_data import tools

#
# Download data
#

# Directory where data will be stored
local_dir = Path('..') / 'data'

# HRRR v4 starts on Dec 3 2020
start_date = datetime(2020, 12, 3)
end_date = datetime(2020, 12, 4)

region = 'conus'
data_type = 'wrfsfc'

init_hour = 12
forecast_hour = 32

grib_files = s3.download_date_range(
    start_date, end_date, region, init_hour, forecast_hour, data_type, local_dir
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
    'Temperature 2 m above ground',
    'Dewpoint temperature 2 m above ground',
    'Relative humidity 2 m above ground',
    'West-east wind velocity',
    'South-north wind velocity',
    'Total 1 h accumulated precipitation',
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

#!/usr/bin/env python

'''
HRRR v4 data are available starting 2020 12 03.

This code lists the variables in a in HRRR v4 data file available on the AWS S3 (Simple Storage System).

The list is saved in a file.
'''

import xarray as xr
import s3fs
import cfgrib

fs = s3fs.S3FileSystem(anon=True)

bucket = 'noaa-hrrr-bdp-pds'
region = 'conus'
file = 'noaa-hrrr-bdp-pds/hrrr.20201203/conus/hrrr.t00z.wrfsfcf24.grib2'

with fs.open(file) as f:
  # List available GRIB messages
  index = cfgrib.open_fileindex(f)
  print(index)

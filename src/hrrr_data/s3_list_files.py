'''
HRRR v4 data are available starting 2020 12 03.

This code lists HRRR v4 data files available on the AWS S3 (Simple Storage System).

The list is saved in a file.
'''

import xarray as xr
import s3fs

fs = s3fs.S3FileSystem(anon=True)

bucket = 'noaa-hrrr-bdp-pds'
region = 'conus'
files = fs.glob(bucket + '/hrrr.20201203/' + region + '/*')

with open('list_S3_HRRRv4_files.txt','w') as f:
  for file in files:
    f.write(file + '\n')

exit()

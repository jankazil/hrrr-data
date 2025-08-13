"""
Retrieve and print information on a file in the S3 HRRR bucket.
"""

from pathlib import Path

from hrrr_data import s3

local_dir = Path('..') / 'data' / 'HRRR'

hrrr_file = 'hrrr.20201203/conus/hrrr.t00z.wrfsfcf24.grib2'

info = s3.info(hrrr_file)

for key, value in info.items():
    print(key, ':', value)

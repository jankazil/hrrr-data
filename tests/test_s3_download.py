"""
Download a given file from the S3 HRRR bucket.
"""

from hrrr_data import s3
from pathlib import Path

local_dir = Path('..') / 'data' / 'HRRR'

hrrr_file = 'hrrr.20201203/conus/hrrr.t00z.wrfsfcf24.grib2'

local_file = s3.download(hrrr_file,local_dir)

print(str(local_file))

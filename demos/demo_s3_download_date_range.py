"""
Download files within a given time range from the S3 HRRR bucket.
"""

from datetime import datetime
from pathlib import Path

from hrrr_data import s3

local_dir = Path('..') / 'data' / 'HRRR'

start_date = datetime(2025, 1, 1)
end_date = datetime(2025, 6, 30)

region = 'conus'
init_hour = 12
forecast_hour = 32

data_type = 'wrfsfc'

local_files = s3.download_date_range(
    start_date, end_date, region, init_hour, forecast_hour, data_type, local_dir
)

print()
print('Local paths to downloaded files')
print()

for local_file in local_files:
    print(str(local_file))

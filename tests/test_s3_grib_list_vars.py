"""
List variables in a GRIB file.
"""

from pathlib import Path
from hrrr_data import s3

file = Path('..') / 'data' / 'HRRR' / 'hrrr.20201203' / 'conus' / 'hrrr.t00z.wrfsfcf24.grib2'

vars = s3.grib_list_vars(file)

for var, name in vars.items():
    print(var,' : ',name)

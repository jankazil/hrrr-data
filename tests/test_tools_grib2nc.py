"""
Convert a given file in GRIB format to netCDF format.
"""

from pathlib import Path
from hrrr_data import tools

grib_file = Path('..') / 'data' / 'HRRR' / 'hrrr.20201203'/ 'conus' / 'hrrr.t00z.wrfsfcf24.grib2'

nc_file = tools.grib2nc(grib_file)

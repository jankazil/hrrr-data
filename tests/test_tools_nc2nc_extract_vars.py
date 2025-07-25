"""
Extracts select variables from a netCDF file and saves them in a separate netCDF file.
"""

from pathlib import Path
from hrrr_data import tools

in_file = Path('..') / 'data' / 'HRRR' / 'hrrr.20201203' / 'conus' / 'hrrr.t00z.wrfsfcf24.nc'

out_file_name = str(in_file.stem) + '_select_vars.nc'

out_file = in_file.parent / out_file_name

variables = [
'TMP_P0_L103_GLC0',
'DPT_P0_L103_GLC0',
'RH_P0_L103_GLC0',
'UGRD_P0_L103_GLC0',
'VGRD_P0_L103_GLC0',
'APCP_P8_L1_GLC0_acc24h',
'APCP_P8_L1_GLC0_acc1h',
]

tools.nc2nc_extract_vars(in_file,out_file,variables)

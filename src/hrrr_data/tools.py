"""
Tools for operations on files in GRIB and netCDF format.
"""

import shutil
import subprocess
from pathlib import Path

import numpy as np
import pygrib
import xarray as xr


def grib_list_vars(file: Path) -> dict[str, str]:
    """
    Returns variable names and their descriptive names as found in a GRIB file.

    Args:
        file (Path): Local file path to a GRIB file

    Returns:
        dict [str,str]: Dictionary of variable names and their descriptive names
    """

    vars = {}  # A dictionary mapping the variables -> descriptive names

    with pygrib.open(str(file)) as grbs:
        # pygrib.open returns a file-like object (a pygrib.open instance),
        # which behaves as an iterator over the GRIB messages in the file.
        for grb in grbs:
            if grb.shortName not in vars:
                vars[grb.shortName] = grb.name

    return vars


def grib2nc(grib_file: Path, verbose: bool = False):
    """
    Converts a file in GRIB format to a file in netCDF format.

    For simplicity, we use an external tool, ncl_convert2nc, which must be installed on the host system.

    If the file in netCDF format exists, it will be overwritten.

    Args:
        grib_file (Path): Local file path to a file in GRIB format.
        verbose (bool, optional): If True, print detailed progress information to stdout. Defaults to False.

    Returns:
        Path: Local file path to a file in netCDF format.
    """

    if shutil.which("ncl_convert2nc") is None:
        print("Warning: ncl_convert2nc is not available on PATH. Skipping conversion to netCDF.")
        return

    # Construct the command

    output_dir = grib_file.parent
    output_file_name = grib_file.stem + '.nc'
    output_file = output_dir / output_file_name

    cmd = ['ncl_convert2nc', str(grib_file), '-o', output_dir]

    # Call the command
    result = subprocess.run(cmd, capture_output=True, text=True)

    # Print output
    if verbose:
        print()
        print('running ncl_convert2nc to produce the file')
        print()
        print(str(output_file))
        print()
        if result.stdout != '':
            print(result.stdout)
        if result.stderr != '':
            print(result.stderr)

    return output_file


def nc2nc_extract_vars(
    in_file: Path,
    out_file: Path,
    variables: list[str],
    long_names: list[str | None] | None = None,
    global_attributes: dict[str, str | None] | None = None,
):
    """
    Extracts given variables from a file in netCDF format and saves them in a file in netCDF format.

    Arguments
    ---------
        in_file (Path):
            File in netCDF format from which the variables will be extracted.
        out_file (Path):
            File in netCDF format in which the variables will be saved. If the file exists, it will be overwritten.
        variables (list of str):
            netCDF variable names.
        long_names (list of str | None, optional):
            Descriptive names for the extracted variables, aligned by position to `variables`.
            If provided, the list length must match `variables`. A value of None leaves the
            variable’s `long_name` unchanged. Defaults to None.
        global_attributes (dict[str, str | None], optional):
            Global attributes to set in the output dataset. Keys are attribute names and
            values are attribute values. A value of None leaves that attribute unchanged.
            Defaults to None.
    """

    # Open the file

    with xr.open_dataset(in_file) as ds:
        # Check for missing variables
        missing_vars = [var for var in variables if var not in ds.variables]
        if missing_vars:
            raise KeyError(
                f'The following variables are not found in the input file: {missing_vars}'
            )

        # Select the requested variables:
        ds_subset = ds[variables]

        # Set the long names of the requested variables

        if long_names is not None:
            for variable, long_name in zip(variables, long_names, strict=False):
                if long_name is not None:
                    ds_subset[variable].attrs['long_name'] = long_name

        # Set the requested global attributes

        if global_attributes is not None:
            for global_attribute in global_attributes:
                if global_attributes[global_attribute] is not None:
                    ds_subset.attrs[global_attribute] = global_attributes[global_attribute]

        # Write to output netCDF file, overwrite if it exists
        ds_subset.to_netcdf(out_file, mode='w')


def nc2nc_process_wind_speed(nc_file: Path):
    """
    If the given file in netCDF format contains the variables

      UGRD_P0_L103_GLC0 (west-east wind speed)
      VGRD_P0_L103_GLC0 (south-north wind speed)

    then

    - the horizontal wind speed is calculated at all levels for which UGRD_P0_L103_GLC0 and VGRD_P0_L103_GLC0 are defined
    - UGRD_P0_L103_GLC0 and VGRD_P0_L103_GLC0 are removed from the netCDF file,
    - the horizontal wind speed is saved in the netCDF file, one variable per level,
    - all other variables in the netCDF file are kept unchanged.

    Arguments
    ---------
        nc_file (Path):
            File in netCDF format.
    """

    # Wind speed variables

    u_var = 'UGRD_P0_L103_GLC0'
    v_var = 'VGRD_P0_L103_GLC0'

    variables = [u_var, v_var]

    # Altitude dimension of wind speed variables

    alt_dim = 'lv_HTGL2'

    # Open the file

    with xr.open_dataset(nc_file) as ds_:
        ds = ds_.load()  # Load all data from disk into memory

        ds_.close()

    # Check if wind speed variables are missing

    missing_vars = [var for var in variables if var not in ds.variables]

    if missing_vars:
        # Do nothing and return.
        return

    # Calculate horizontal wind speed
    wind_speed = np.sqrt(ds[u_var] ** 2 + ds[v_var] ** 2)

    if alt_dim in wind_speed.dims:
        for alt_i in range(ds.sizes[alt_dim]):
            alt_string_int = str(int(np.round(ds[alt_dim][alt_i].item())))
            alt_string_float = str(np.round(ds[alt_dim][alt_i].item(), 3))

            ds['WS' + alt_string_int] = wind_speed.isel({alt_dim: alt_i})

            ds['WS' + alt_string_int].attrs['initial_time'] = ds[u_var].attrs['initial_time']
            ds['WS' + alt_string_int].attrs['forecast_time_units'] = ds[u_var].attrs[
                'forecast_time_units'
            ]
            ds['WS' + alt_string_int].attrs['forecast_time'] = ds[u_var].attrs['forecast_time']
            ds['WS' + alt_string_int].attrs['level_type'] = ds[u_var].attrs['level_type']
            ds['WS' + alt_string_int].attrs['parameter_template_discipline_category_number'] = ds[
                u_var
            ].attrs['parameter_template_discipline_category_number']
            ds['WS' + alt_string_int].attrs['parameter_discipline_and_category'] = ds[u_var].attrs[
                'parameter_discipline_and_category'
            ]
            ds['WS' + alt_string_int].attrs['grid_type'] = ds[u_var].attrs['grid_type']
            ds['WS' + alt_string_int].attrs['units'] = ds[u_var].attrs['units']
            ds['WS' + alt_string_int].attrs['long_name'] = (
                'Horizontal wind speed at ' + alt_string_float + ' ' + ds[alt_dim].attrs['units']
            )
            ds['WS' + alt_string_int].attrs['production_status'] = ds[u_var].attrs[
                'production_status'
            ]
            ds['WS' + alt_string_int].attrs['center'] = ds[u_var].attrs['center']

    else:
        ds['WS'] = wind_speed

        ds['WS'].attrs['initial_time'] = ds[u_var].attrs['initial_time']
        ds['WS'].attrs['forecast_time_units'] = ds[u_var].attrs['forecast_time_units']
        ds['WS'].attrs['forecast_time'] = ds[u_var].attrs['forecast_time']
        ds['WS'].attrs['level_type'] = ds[u_var].attrs['level_type']
        ds['WS'].attrs['parameter_template_discipline_category_number'] = ds[u_var].attrs[
            'parameter_template_discipline_category_number'
        ]
        ds['WS'].attrs['parameter_discipline_and_category'] = ds[u_var].attrs[
            'parameter_discipline_and_category'
        ]
        ds['WS'].attrs['grid_type'] = ds[u_var].attrs['grid_type']
        ds['WS'].attrs['units'] = ds[u_var].attrs['units']
        ds['WS'].attrs['long_name'] = 'Horizontal wind speed'
        ds['WS'].attrs['production_status'] = ds[u_var].attrs['production_status']
        ds['WS'].attrs['center'] = ds[u_var].attrs['center']

    # Remove original wind speed variables
    ds = ds.drop_vars(variables)

    # Write to output netCDF file, overwrite if it exists
    ds.to_netcdf(nc_file)

    return


def extract_select_sfc_vars_to_netcdf(grib_file: Path, verbose: bool = False) -> Path:
    '''
    Convert GRIB2 to netCDF and extract selected surface variables into a new file.

    Returns the path to the netCDF file.
    '''
    VARIABLES = [
        "TMP_P0_L103_GLC0",
        "DPT_P0_L103_GLC0",
        "RH_P0_L103_GLC0",
        "UGRD_P0_L103_GLC0",
        "VGRD_P0_L103_GLC0",
        "APCP_P8_L1_GLC0_acc1h",
    ]

    LONG_NAMES = [
        "Air temperature at 2 m above ground",
        "Dew point temperature at 2 m above ground",
        "Relative humidity at 2 m above ground",
        "West-east wind speed",
        "South-north wind speed",
        "1 h accumulated precipitation",
    ]

    GLOBAL_ATTRS = {
        "model": "HRRR",
        "processed_with": "https://github.com/jankazil/hrrr-data",
    }

    # Convert the file from GRIB2 to netCDF
    ncfile_full = grib2nc(grib_file, verbose=verbose)

    # Name for file that will contain the selected variables
    ncfile_new = ncfile_full

    # Rename the full file to a temporary file
    ncfile_tmp_name = str(ncfile_full.name) + '.tmp'
    ncfile_tmp = ncfile_full.parent / Path(ncfile_tmp_name)
    ncfile_full.replace(ncfile_tmp)

    # Extract select variables

    nc2nc_extract_vars(
        ncfile_tmp,
        ncfile_new,
        VARIABLES,
        long_names=LONG_NAMES,
        global_attributes=GLOBAL_ATTRS,
    )

    # Process wind speed

    nc2nc_process_wind_speed(ncfile_new)

    ncfile_tmp.unlink()

    return ncfile_new

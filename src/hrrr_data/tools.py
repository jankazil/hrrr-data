'''
Tools for operations on files in GRIB and netCDF format.
'''

import warnings
from pathlib import Path

import numpy as np
import pygrib
import xarray as xr
from netCDF4 import Dataset

# GRIB fields to extract into netCDF files

_SFC_GRIB_FIELDS = {
    'TMP_P0_L103_GLC0': {
        'long_name': 'Air temperature at 2 m above ground',
        'selector': {
            'discipline': 0,
            'parameterCategory': 0,
            'parameterNumber': 0,
            'typeOfLevel': 'heightAboveGround',
            'level': 2,
        },
    },
    'DPT_P0_L103_GLC0': {
        'long_name': 'Dew point temperature at 2 m above ground',
        'selector': {
            'discipline': 0,
            'parameterCategory': 0,
            'parameterNumber': 6,
            'typeOfLevel': 'heightAboveGround',
            'level': 2,
        },
    },
    'U10': {
        'long_name': 'West-east wind speed at 10.0 m',
        'selector': {
            'discipline': 0,
            'parameterCategory': 2,
            'parameterNumber': 2,
            'typeOfLevel': 'heightAboveGround',
            'level': 10,
        },
    },
    'V10': {
        'long_name': 'South-north wind speed at 10.0 m',
        'selector': {
            'discipline': 0,
            'parameterCategory': 2,
            'parameterNumber': 3,
            'typeOfLevel': 'heightAboveGround',
            'level': 10,
        },
    },
}


def grib_list_vars(file: Path) -> dict[str, str]:
    '''
    Returns variable names and their descriptive names as found in a GRIB file.

    Args:
        file (Path): Local file path to a GRIB file

    Returns:
        dict [str,str]: Dictionary of variable names and their descriptive names
    '''

    vars = {}  # A dictionary mapping the variables -> descriptive names

    with pygrib.open(str(file)) as grbs:
        # pygrib.open returns a file-like object (a pygrib.open instance),
        # which behaves as an iterator over the GRIB messages in the file.
        for grb in grbs:
            if grb.shortName not in vars:
                vars[grb.shortName] = grb.name

    return vars


def grib2nc(grib_file: Path, verbose: bool = False) -> Path:
    '''
    Extract the supported HRRR surface fields from GRIB2 and write netCDF.

    The GRIB messages are selected with ``pygrib.open.select`` using numerical
    GRIB2 parameter identifiers, level type, and level. In particular, U10 and
    V10 are selected directly at 10 m rather than by relying on the ordering of
    a combined height dimension.

    Parameters
    ----------
    grib_file : Path
        Local path to the input GRIB file.
    verbose : bool, optional
        If True, print the selected GRIB messages and output path. Defaults to
        False.

    Returns
    -------
    Path
        Local path to the generated netCDF file.

    Raises
    ------
    FileNotFoundError
        If the input GRIB file does not exist.
    ValueError
        If any required field is missing or has more than one matching message,
        or if the selected fields do not use the same horizontal grid.
    '''
    grib_file = grib_file.expanduser().resolve()
    if not grib_file.is_file():
        raise FileNotFoundError(f'GRIB file does not exist: {grib_file}')

    output_file = grib_file.with_suffix('.nc')
    temporary_output_file = output_file.with_name(output_file.name + '.tmp')

    try:
        if temporary_output_file.exists():
            temporary_output_file.unlink()

        with (
            pygrib.open(str(grib_file)) as grbs,
            Dataset(temporary_output_file, mode='w', format='NETCDF4') as nc,
        ):
            nc.setncatts(
                {
                    'model': 'HRRR',
                    'processed_with': 'https://github.com/jankazil/hrrr-data',
                }
            )

            reference_shape = None

            for variable, field in _SFC_GRIB_FIELDS.items():
                grb = _select_one_grib_message(grbs, variable, field['selector'])
                shape = (grb.Ny, grb.Nx)

                if reference_shape is None:
                    reference_shape = shape
                    nc.createDimension('ygrid_0', shape[0])
                    nc.createDimension('xgrid_0', shape[1])

                    latitude, longitude = grb.latlons()

                    latitude_out = nc.createVariable(
                        'gridlat_0', np.float32, ('ygrid_0', 'xgrid_0')
                    )
                    latitude_out.setncatts({'long_name': 'latitude', 'units': 'degrees_north'})
                    latitude_out[:] = np.asarray(latitude, dtype=np.float32)
                    del latitude, latitude_out

                    longitude_out = nc.createVariable(
                        'gridlon_0', np.float32, ('ygrid_0', 'xgrid_0')
                    )
                    longitude_out.setncatts({'long_name': 'longitude', 'units': 'degrees_east'})
                    longitude_out[:] = np.asarray(longitude, dtype=np.float32)
                    del longitude, longitude_out
                elif shape != reference_shape:
                    raise ValueError(
                        f'GRIB message {variable!r} has shape {shape}, expected {reference_shape}'
                    )

                variable_out = nc.createVariable(
                    variable,
                    np.float32,
                    ('ygrid_0', 'xgrid_0'),
                    fill_value=np.float32(9.96921e36),
                )
                attrs = _grib_message_attrs(grb, field['long_name'])
                attrs['coordinates'] = 'gridlat_0 gridlon_0'
                variable_out.setncatts(attrs)

                values = np.ma.asarray(grb.values, dtype=np.float32)
                variable_out[:] = values
                del values, variable_out

                if verbose:
                    print('selected:', variable, grb, flush=True)

        temporary_output_file.replace(output_file)
    finally:
        if temporary_output_file.exists():
            temporary_output_file.unlink()

    if verbose:
        print('created:', output_file, flush=True)

    return output_file


def nc2nc_extract_vars(
    in_file: Path,
    out_file: Path,
    variables: list[str],
    long_names: list[str | None] | None = None,
    global_attributes: dict[str, str | None] | None = None,
):
    '''
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
    '''

    # Open the file

    with xr.open_dataset(in_file) as ds:
        # Check for missing variables
        missing_vars = [var for var in variables if var not in ds.variables]
        if missing_vars:
            warnings.warn(
                f'The following variables are not present in the input file {in_file}: {missing_vars}',
                category=UserWarning,
                stacklevel=2,
            )

        # Variables available in the file
        variables = [v for v in variables if v not in missing_vars]

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
    '''
    If the given file in netCDF format contains the variables

      UGRD_P0_L103_GLC0 (west-east wind speed)
      VGRD_P0_L103_GLC0 (south-north wind speed)

    then

    - Individual (U,V) wind speed variables are created for each altitude at which wind speed is given
    - The wind speed variables UGRD_P0_L103_GLC0 and VGRD_P0_L103_GLC0 are removed,
    - all other variables in the netCDF file are kept unchanged.

    Arguments
    ---------
        nc_file (Path):
            File in netCDF format.
    '''

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

    #
    # Create individual (U,V) wind speed variables for each altitude at which wind speed is given
    #

    wind_var_names = ['U', 'V']
    wind_var_long_names = ['West-east wind speed', 'South-north wind speed']
    wind_vars = [ds[u_var], ds[v_var]]

    attrs_to_copy = [
        'initial_time',
        'forecast_time_units',
        'forecast_time',
        'level_type',
        'parameter_template_discipline_category_number',
        'parameter_discipline_and_category',
        'grid_type',
        'units',
        'production_status',
        'center',
    ]

    if all(alt_dim in wind_var.dims for wind_var in wind_vars):
        seen_names = set()

        for alt_i in range(1):
            alt_value = ds[alt_dim][alt_i].item()
            alt_string_int = str(int(np.round(alt_value)))
            alt_string_float = str(np.round(alt_value, 3))

            for wind_var_name, wind_var_long_name, wind_var in zip(
                wind_var_names, wind_var_long_names, wind_vars, strict=True
            ):
                new_var_name = wind_var_name + alt_string_int

                if new_var_name in seen_names or new_var_name in ds:
                    raise ValueError(f'Duplicate output variable name: {new_var_name}')

                seen_names.add(new_var_name)

                ds[new_var_name] = wind_var.isel({alt_dim: alt_i})

                for attr_name in attrs_to_copy:
                    ds[new_var_name].attrs[attr_name] = wind_var.attrs[attr_name]

                ds[new_var_name].attrs['long_name'] = (
                    wind_var_long_name
                    + ' at '
                    + alt_string_float
                    + ' '
                    + ds[alt_dim].attrs['units']
                )

    else:
        for wind_var_name, wind_var_long_name, wind_var in zip(
            wind_var_names, wind_var_long_names, wind_vars, strict=True
        ):
            ds[wind_var_name] = wind_var

            for attr_name in attrs_to_copy:
                ds[wind_var_name].attrs[attr_name] = wind_var.attrs[attr_name]

            ds[wind_var_name].attrs['long_name'] = wind_var_long_name

    # Remove original wind speed variables
    ds = ds.drop_vars(variables)

    # Write to output netCDF file, overwrite if it exists
    ds.to_netcdf(nc_file)

    return


def extract_select_sfc_vars_to_netcdf(
    grib_file: Path, refresh: bool = True, verbose: bool = False
) -> Path:
    '''
    Convert a GRIB file to a netCDF file containing only selected surface meteorological variables.

    This function first checks whether a processed netCDF file already exists for the given GRIB input.
    If not, or if reprocessing is requested, it converts the GRIB file to netCDF format, extracts key
    near-surface variables such as temperature, dew point, wind components, adds descriptive metadata,
    computes derived wind speed fields, and writes the results to a new netCDF file in the same directory.

    Parameters
    ----------
    grib_file : Path
        Path to the input GRIB file containing HRRR model output.
    refresh : bool, optional
        If True, convert the GRIB file and extract variables even if a corresponding netCDF file already exists.
        Default is True.
    verbose : bool, optional
        If True, print progress messages during processing. Default is False.

    Returns
    -------
    Path
        Path to the resulting netCDF file containing the selected surface variables.
    '''

    # netCDF file to be created
    ncfile = grib_file.with_suffix('.nc')

    if refresh or not ncfile.exists():
        if verbose:
            print(flush=True)
            print(
                'Converting and extracting selected surface variables from',
                grib_file,
                '->',
                ncfile,
                flush=True,
            )

        grib2nc(grib_file, verbose=verbose)

    else:
        if verbose:
            print(flush=True)
            print(
                'Conversion',
                grib_file,
                '->',
                ncfile,
                'skipped - file exists and refresh =',
                refresh,
                flush=True,
            )

    return ncfile


def _select_one_grib_message(grbs, variable: str, selector: dict[str, object]):
    '''Select exactly one GRIB message using the supplied ecCodes keys.'''
    try:
        messages = grbs.select(**selector)
    except ValueError:
        messages = []

    if len(messages) != 1:
        raise ValueError(
            f'Expected one GRIB message for {variable!r}, found {len(messages)}; '
            f'selector: {selector}'
        )

    return messages[0]


def _grib_message_attrs(grb, long_name: str) -> dict[str, str | int | list[int]]:
    '''Return the metadata needed by the existing plotting and analysis code.'''
    forecast_time = int(round((grb.validDate - grb.analDate).total_seconds() / 3600))
    units = 'm/s' if grb.units == 'm s**-1' else grb.units

    return {
        'initial_time': grb.analDate.strftime('%m/%d/%Y (%H:%M)'),
        'forecast_time_units': 'hours',
        'forecast_time': forecast_time,
        'level_type': grb.typeOfLevel,
        'parameter_template_discipline_category_number': [
            grb.productDefinitionTemplateNumber,
            grb.discipline,
            grb.parameterCategory,
            grb.parameterNumber,
        ],
        'parameter_discipline_and_category': [grb.discipline, grb.parameterCategory],
        'grid_type': grb.gridType,
        'units': units,
        'production_status': grb.productionStatusOfProcessedData,
        'center': grb.centreDescription,
        'long_name': long_name,
    }

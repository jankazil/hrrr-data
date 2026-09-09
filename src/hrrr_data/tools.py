'''
Tools for operations on data in GRIB, Zarr, and netCDF formats.
'''

import warnings
from contextlib import ExitStack
from datetime import datetime
from pathlib import Path

import numpy as np
import pygrib
import xarray as xr
from netCDF4 import Dataset

from hrrr_data import s3

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
    'APCP_P8_L1_GLC0_acc1h': {
        'long_name': 'Total precipitation accumulated over 1 hour',
        'selector': {
            'discipline': 0,
            'parameterCategory': 1,
            'parameterNumber': 8,
            'typeOfLevel': 'surface',
            'level': 0,
            'stepType': 'accum',
            'lengthOfTimeRange': 1,
        },
    },
}


# Zarr fields to extract into netCDF files. Forecast hour 0 is not included in
# these forecast arrays; it is stored separately in an analysis Zarr store.

_SFC_ZARR_FIELDS = {
    'TMP_P0_L103_GLC0': {
        'zarr_group': '2m_above_ground/TMP/2m_above_ground',
        'zarr_variable': 'TMP',
        'long_name': 'Air temperature at 2 m above ground',
        'level_type': 'heightAboveGround',
        'parameter_category': 0,
        'parameter_number': 0,
        'product_definition_template': 0,
        'units': 'K',
    },
    'DPT_P0_L103_GLC0': {
        'zarr_group': '2m_above_ground/DPT/2m_above_ground',
        'zarr_variable': 'DPT',
        'long_name': 'Dew point temperature at 2 m above ground',
        'level_type': 'heightAboveGround',
        'parameter_category': 0,
        'parameter_number': 6,
        'product_definition_template': 0,
        'units': 'K',
    },
    'U10': {
        'zarr_group': '10m_above_ground/UGRD/10m_above_ground',
        'zarr_variable': 'UGRD',
        'long_name': 'West-east wind speed at 10.0 m',
        'level_type': 'heightAboveGround',
        'parameter_category': 2,
        'parameter_number': 2,
        'product_definition_template': 0,
        'units': 'm/s',
    },
    'V10': {
        'zarr_group': '10m_above_ground/VGRD/10m_above_ground',
        'zarr_variable': 'VGRD',
        'long_name': 'South-north wind speed at 10.0 m',
        'level_type': 'heightAboveGround',
        'parameter_category': 2,
        'parameter_number': 3,
        'product_definition_template': 0,
        'units': 'm/s',
    },
    'APCP_P8_L1_GLC0_acc1h': {
        'zarr_group': 'surface/APCP_1hr_acc_fcst/surface',
        'zarr_variable': 'APCP_1hr_acc_fcst',
        'long_name': 'Total precipitation accumulated over 1 hour',
        'level_type': 'surface',
        'parameter_category': 1,
        'parameter_number': 8,
        'product_definition_template': 8,
        'units': 'kg m**-2',
    },
}


_GRID_LATITUDE: np.ndarray | None = None
_GRID_LONGITUDE: np.ndarray | None = None


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
        except for 1-hour accumulated precipitation at forecast lead hour 0,
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
            forecast_lead_hour = None

            for variable, field in _SFC_GRIB_FIELDS.items():
                if variable == 'APCP_P8_L1_GLC0_acc1h' and forecast_lead_hour == 0:
                    try:
                        matching_grbs = grbs.select(**field['selector'])
                    except ValueError:
                        matching_grbs = []

                    if not matching_grbs:
                        print(
                            'skipped: APCP_P8_L1_GLC0_acc1h is not present '
                            'or required at forecast lead hour 0',
                            flush=True,
                        )
                        continue

                grb = _select_one_grib_message(grbs, variable, field['selector'])

                if forecast_lead_hour is None:
                    forecast_lead_hour = int(
                        round((grb.validDate - grb.analDate).total_seconds() / 3600)
                    )

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
            variable's `long_name` unchanged. Defaults to None.
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


def extract_select_sfc_zarr_vars_to_netcdf(
    date: datetime,
    init_hour: int,
    first_forecast_lead_hour: int,
    last_forecast_lead_hour: int,
    region: str,
    local_dir: Path,
    refresh: bool = False,
    verbose: bool = False,
) -> list[Path]:
    '''
    Read selected surface variables from one HRRR forecast Zarr store and
    create one compatible netCDF file per requested forecast hour.

    The forecast-hour range is inclusive and must begin at hour 1 or later.
    Forecast hour 0 is stored separately as an analysis and is not supported.

    Parameters
    ----------
    date : datetime
        Date on which the forecast was initialized.
    init_hour : int
        Forecast initialization hour in UTC.
    first_forecast_lead_hour : int
        First forecast lead hour to write, inclusive.
    last_forecast_lead_hour : int
        Last forecast lead hour to write, inclusive.
    region : str
        Geographic region identifier. The traditional Zarr archive supports
        only ``'conus'``.
    local_dir : Path
        Directory in which the netCDF files will be created.
    refresh : bool, optional
        If True, recreate files that already exist. Defaults to False.
    verbose : bool, optional
        If True, print progress messages. Defaults to False.

    Returns
    -------
    list[Path]
        Paths of all requested netCDF files, including existing files retained
        when ``refresh`` is False.
    '''

    output_files = [
        _zarr_netcdf_path(local_dir, date, init_hour, forecast_lead_hour, region)
        for forecast_lead_hour in range(first_forecast_lead_hour, last_forecast_lead_hour + 1)
    ]

    files_to_create = [
        output_file for output_file in output_files if refresh or not output_file.exists()
    ]

    if not files_to_create:
        if verbose:
            print(
                'All requested netCDF files already exist for the HRRR forecast '
                f'initialized on {date:%Y-%m-%d} at {init_hour:02d} UTC. '
                'Skipping remote Zarr access.',
                flush=True,
            )
        return output_files

    if verbose:
        print(
            'Reading from the HRRR Zarr archive the inclusive forecast-hour range',
            f'{first_forecast_lead_hour}-{last_forecast_lead_hour}',
            'for the forecast initialized on',
            f'{date:%Y-%m-%d} at {init_hour:02d} UTC.',
            'Forecast hour 0 is not supported by this script.',
            flush=True,
        )

    store, zarr_url = s3.zarr_forecast_store(date, init_hour)

    coordinate_group = '2m_above_ground/TMP'
    with xr.open_zarr(
        store,
        group=coordinate_group,
        consolidated=True,
        chunks=None,
        decode_times=False,
        mask_and_scale=False,
    ) as coordinate_ds:
        forecast_periods = np.asarray(coordinate_ds['forecast_period'].values, dtype=np.int64)

    lead_indices = _zarr_forecast_lead_indices(
        forecast_periods,
        first_forecast_lead_hour,
        last_forecast_lead_hour,
        zarr_url,
    )

    latitude, longitude = _load_zarr_grid_coordinates()
    requested_output = {
        forecast_lead_hour: output_file
        for forecast_lead_hour, output_file in zip(
            range(first_forecast_lead_hour, last_forecast_lead_hour + 1),
            output_files,
            strict=True,
        )
        if refresh or not output_file.exists()
    }

    _write_zarr_netcdf_files(
        store,
        date,
        init_hour,
        lead_indices,
        requested_output,
        latitude,
        longitude,
        verbose,
    )

    return output_files


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


def _write_zarr_netcdf_files(
    store,
    date: datetime,
    init_hour: int,
    lead_indices: dict[int, int],
    requested_output: dict[int, Path],
    latitude: np.ndarray,
    longitude: np.ndarray,
    verbose: bool,
) -> None:
    '''Write selected Zarr forecast periods to separate, atomic netCDF files.'''

    temporary_files = {
        forecast_lead_hour: output_file.with_name(output_file.name + '.tmp')
        for forecast_lead_hour, output_file in requested_output.items()
    }

    for output_file in requested_output.values():
        output_file.parent.mkdir(parents=True, exist_ok=True)

    try:
        for temporary_file in temporary_files.values():
            if temporary_file.exists():
                temporary_file.unlink()

        with ExitStack() as stack:
            netcdf_files = {
                forecast_lead_hour: stack.enter_context(
                    Dataset(temporary_file, mode='w', format='NETCDF4')
                )
                for forecast_lead_hour, temporary_file in temporary_files.items()
            }

            for netcdf_file in netcdf_files.values():
                _initialize_zarr_netcdf_file(netcdf_file, latitude, longitude)

            first_index = min(lead_indices.values())
            last_index = max(lead_indices.values())
            zarr_time_slice = slice(first_index, last_index + 1)

            for variable, field in _SFC_ZARR_FIELDS.items():
                with xr.open_zarr(
                    store,
                    group=field['zarr_group'],
                    consolidated=True,
                    chunks=None,
                    decode_times=False,
                    mask_and_scale=False,
                ) as field_ds:
                    zarr_variable = field_ds[field['zarr_variable']]
                    _validate_zarr_variable(zarr_variable, variable, latitude.shape)

                    values = np.asarray(
                        zarr_variable.isel(time=zarr_time_slice).values,
                        dtype=np.float32,
                    )
                    zarr_fill_value = zarr_variable.encoding.get(
                        '_FillValue', zarr_variable.attrs.get('_FillValue')
                    )

                for forecast_lead_hour, netcdf_file in netcdf_files.items():
                    variable_out = netcdf_file.createVariable(
                        variable,
                        np.float32,
                        ('ygrid_0', 'xgrid_0'),
                        fill_value=np.float32(9.96921e36),
                    )
                    variable_out.setncatts(
                        _zarr_variable_attributes(field, date, init_hour, forecast_lead_hour)
                    )

                    relative_index = lead_indices[forecast_lead_hour] - first_index
                    variable_out[:] = _masked_zarr_values(values[relative_index], zarr_fill_value)

                    if verbose:
                        print(
                            'Selected:',
                            variable,
                            f'forecast hour {forecast_lead_hour}',
                            flush=True,
                        )

                del values

        for forecast_lead_hour, temporary_file in temporary_files.items():
            output_file = requested_output[forecast_lead_hour]
            temporary_file.replace(output_file)
            if verbose:
                print('Created:', output_file, flush=True)

    finally:
        for temporary_file in temporary_files.values():
            if temporary_file.exists():
                temporary_file.unlink()


def _initialize_zarr_netcdf_file(
    netcdf_file: Dataset,
    latitude: np.ndarray,
    longitude: np.ndarray,
) -> None:
    '''Initialize dimensions, coordinates, and global metadata in a netCDF file.'''

    netcdf_file.setncatts(
        {
            'model': 'HRRR',
            'processed_with': 'https://github.com/jankazil/hrrr-data',
            'source_format': 'Zarr',
            'source_archive': 's3://hrrrzarr',
        }
    )

    netcdf_file.createDimension('ygrid_0', latitude.shape[0])
    netcdf_file.createDimension('xgrid_0', latitude.shape[1])

    latitude_out = netcdf_file.createVariable('gridlat_0', np.float32, ('ygrid_0', 'xgrid_0'))
    latitude_out.setncatts({'long_name': 'latitude', 'units': 'degrees_north'})
    latitude_out[:] = latitude

    longitude_out = netcdf_file.createVariable('gridlon_0', np.float32, ('ygrid_0', 'xgrid_0'))
    longitude_out.setncatts({'long_name': 'longitude', 'units': 'degrees_east'})
    longitude_out[:] = longitude


def _zarr_variable_attributes(
    field: dict[str, object],
    date: datetime,
    init_hour: int,
    forecast_lead_hour: int,
) -> dict[str, str | int | list[int]]:
    '''Return metadata compatible with the existing GRIB-to-netCDF output.'''

    initialization = datetime(date.year, date.month, date.day, init_hour)
    parameter_category = int(field['parameter_category'])
    parameter_number = int(field['parameter_number'])

    return {
        'initial_time': initialization.strftime('%m/%d/%Y (%H:%M)'),
        'forecast_time_units': 'hours',
        'forecast_time': forecast_lead_hour,
        'level_type': str(field['level_type']),
        'parameter_template_discipline_category_number': [
            int(field['product_definition_template']),
            0,
            parameter_category,
            parameter_number,
        ],
        'parameter_discipline_and_category': [0, parameter_category],
        'grid_type': 'lambert',
        'units': str(field['units']),
        'production_status': 0,
        'center': 'US National Weather Service - NCEP',
        'long_name': str(field['long_name']),
        'coordinates': 'gridlat_0 gridlon_0',
    }


def _load_zarr_grid_coordinates() -> tuple[np.ndarray, np.ndarray]:
    '''Load and cache the static HRRR CONUS latitude and longitude grids.'''

    global _GRID_LATITUDE, _GRID_LONGITUDE

    if _GRID_LATITUDE is None or _GRID_LONGITUDE is None:
        grid_store = s3.zarr_grid_store()

        with xr.open_zarr(
            grid_store,
            consolidated=True,
            chunks=None,
            decode_times=False,
            mask_and_scale=False,
        ) as grid_ds:
            _GRID_LATITUDE = np.asarray(grid_ds['latitude'].values, dtype=np.float32)
            _GRID_LONGITUDE = np.asarray(grid_ds['longitude'].values, dtype=np.float32)

    return _GRID_LATITUDE, _GRID_LONGITUDE


def _zarr_forecast_lead_indices(
    forecast_periods: np.ndarray,
    first_forecast_lead_hour: int,
    last_forecast_lead_hour: int,
    zarr_url: str,
) -> dict[int, int]:
    '''Map requested forecast lead hours to positions in a forecast Zarr store.'''

    period_to_index = {
        int(forecast_period): index for index, forecast_period in enumerate(forecast_periods)
    }
    requested_hours = range(first_forecast_lead_hour, last_forecast_lead_hour + 1)
    missing_hours = [hour for hour in requested_hours if hour not in period_to_index]

    if missing_hours:
        if period_to_index:
            available = f'{min(period_to_index)}-{max(period_to_index)}'
        else:
            available = 'none'
        raise ValueError(
            f'Forecast hours {missing_hours} are unavailable in {zarr_url}; '
            f'available forecast hours: {available}. Forecast hour 0 is not '
            'supported because it is stored separately as an analysis.'
        )

    lead_indices = {hour: period_to_index[hour] for hour in requested_hours}
    indices = list(lead_indices.values())
    if indices != list(range(indices[0], indices[-1] + 1)):
        raise ValueError('Requested forecast hours are not stored contiguously in ' + zarr_url)

    return lead_indices


def _validate_zarr_variable(
    zarr_variable: xr.DataArray,
    output_variable: str,
    expected_shape: tuple[int, int],
) -> None:
    '''Validate a remote Zarr variable before it is written to netCDF.'''

    expected_dimensions = (
        'time',
        'projection_y_coordinate',
        'projection_x_coordinate',
    )
    if zarr_variable.dims != expected_dimensions:
        raise ValueError(
            f'Zarr variable for {output_variable!r} has dimensions '
            f'{zarr_variable.dims}, expected {expected_dimensions}'
        )

    if zarr_variable.shape[-2:] != expected_shape:
        raise ValueError(
            f'Zarr variable for {output_variable!r} has horizontal shape '
            f'{zarr_variable.shape[-2:]}, expected {expected_shape}'
        )


def _masked_zarr_values(values: np.ndarray, fill_value: object) -> np.ma.MaskedArray:
    '''Mask nonfinite values and the Zarr fill value.'''

    mask = ~np.isfinite(values)
    if fill_value is not None:
        try:
            fill_value_float = float(fill_value)
        except (TypeError, ValueError):
            fill_value_float = np.nan
        if np.isfinite(fill_value_float):
            mask |= values == np.float32(fill_value_float)

    return np.ma.array(values, mask=mask, copy=False)


def _zarr_netcdf_path(
    local_dir: Path,
    date: datetime,
    init_hour: int,
    forecast_lead_hour: int,
    region: str,
) -> Path:
    '''Construct a netCDF path compatible with the existing GRIB workflow.'''

    date_string = date.strftime('%Y%m%d')
    filename = (
        'hrrr.t' + str(init_hour).zfill(2) + 'z.wrfsfcf' + str(forecast_lead_hour).zfill(2) + '.nc'
    )
    return Path(local_dir) / ('hrrr.' + date_string) / region / filename

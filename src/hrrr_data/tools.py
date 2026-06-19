'''
Tools for operations on files in GRIB and netCDF format.
'''

import os
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pygrib
import xarray as xr


def active_python_env_subprocess_env() -> dict[str, str]:
    '''
    Return a subprocess environment consistent with the active Python
    environment.

    This is needed for Jupyter kernels that use the correct Python executable
    but inherit an incomplete conda environment, for example a wrong
    CONDA_PREFIX or PATH.
    '''
    env = os.environ.copy()

    env_prefix = Path(sys.prefix)
    env_bin = env_prefix / 'bin'

    env['CONDA_PREFIX'] = str(env_prefix)
    env['PATH'] = str(env_bin) + os.pathsep + env.get('PATH', '')

    return env


def find_executable(name: str, env_var: str | None = None) -> Path:
    '''
    Find an external executable, preferring an explicit override and then the
    active Python environment.

    The lookup order is:

    1. If ``env_var`` is given and that environment variable is set, interpret its
       value as the executable path. A leading ``~`` is expanded. If the referenced
       file exists and is a regular file, that path is returned. If the environment
       variable is set but does not point to an existing file, a ``RuntimeError`` is
       raised.
    2. Look for ``name`` in the ``bin`` directory of the active Python environment,
       as determined by ``sys.prefix``.
    3. Fall back to normal ``PATH`` resolution using ``shutil.which``.

    This avoids accidentally using a system executable when Python is running from
    a virtual environment or conda environment whose ``bin`` directory is not first
    on ``PATH``. This can occur, for example, in Jupyter kernels that use the
    correct Python executable but inherit an incomplete shell environment.

    Parameters
    ----------
    name : str
        Name of the executable to find, for example ``'ncl_convert2nc'``.
    env_var : str or None, optional
        Name of an environment variable that may contain an explicit path to the
        executable. If None, no override environment variable is checked.
        Defaults to None.

    Returns
    -------
    Path
        Path to the resolved executable.

    Raises
    ------
    RuntimeError
        If ``env_var`` is set but does not point to an existing regular file, or if
        the executable cannot be found in the active Python environment or on
        ``PATH``.
    '''
    if env_var is not None:
        override = os.environ.get(env_var)
        if override:
            exe = Path(override).expanduser()
            if exe.exists() and exe.is_file():
                return exe
            raise RuntimeError(f'{env_var} is set to {override!r}, but that file does not exist.')

    env_bin = Path(sys.prefix) / 'bin' / name

    if env_bin.exists() and env_bin.is_file():
        return env_bin

    path_exe = shutil.which(name)

    if path_exe is not None:
        return Path(path_exe)

    raise RuntimeError(f'Could not find executable {name!r}. Expected it in {env_bin} or on PATH.')


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
    Convert a GRIB file to netCDF format using ``ncl_convert2nc``.

    The conversion is performed by the external ``ncl_convert2nc`` executable.
    The executable is resolved with :func:`find_executable`, which should prefer
    the executable installed in the active Python environment before falling back
    to the system ``PATH``. This is important in Jupyter kernels, where the Python
    interpreter may belong to a conda environment while ``PATH`` may still point to
    system executables.

    The subprocess is run with an environment adjusted to match the active Python
    environment. In particular, the active Python environment's ``bin`` directory
    is prepended to ``PATH`` and ``CONDA_PREFIX`` is set from ``sys.prefix``. This
    avoids failures in Jupyter kernels that use the correct Python executable but
    inherit incomplete or incorrect conda environment variables.

    The input path is expanded and resolved before conversion. The output file is
    written to the same directory as ``grib_file`` and has the same stem with a
    ``.nc`` suffix. If a file with that name already exists, ``ncl_convert2nc`` may
    overwrite it.

    Parameters
    ----------
    grib_file : Path
        Local path to the input GRIB file.
    verbose : bool, optional
        If True, print diagnostic information, including the resolved
        ``ncl_convert2nc`` executable, the command being run, the expected output
        file, the subprocess return code, and any captured stdout/stderr.
        Defaults to False.

    Returns
    -------
    Path
        Local path to the generated netCDF file.

    Raises
    ------
    RuntimeError
        If ``ncl_convert2nc`` exits with a nonzero return code.
    FileNotFoundError
        If ``ncl_convert2nc`` completes successfully but the expected netCDF output
        file is not created.

    Notes
    -----
    This function checks both the subprocess return code and the existence of the
    expected output file. This avoids masking failures from ``ncl_convert2nc`` as
    later file-operation errors. If the expected output is missing, the error
    message includes nearby files and captured subprocess output to help diagnose
    whether ``ncl_convert2nc`` wrote a differently named file or failed silently.
    '''

    exe = find_executable('ncl_convert2nc')

    grib_file = grib_file.expanduser().resolve()
    output_dir = grib_file.parent
    output_file = output_dir / (grib_file.stem + '.nc')

    cmd = [str(exe), str(grib_file), '-o', str(output_dir)]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        env=active_python_env_subprocess_env(),
    )

    if verbose:
        print()
        print('running ncl_convert2nc')
        print('executable:', exe)
        print('command:', cmd)
        print('expected output:', output_file)
        print('return code:', result.returncode)
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr)

    if result.returncode != 0:
        raise RuntimeError(
            'ncl_convert2nc failed\n'
            f'executable: {exe}\n'
            f'command: {cmd}\n'
            f'return code: {result.returncode}\n'
            f'stdout:\n{result.stdout}\n'
            f'stderr:\n{result.stderr}'
        )

    if not output_file.exists():
        similar_files = sorted(output_dir.glob(grib_file.stem + '*.nc'))
        nearby_files = sorted(output_dir.glob(grib_file.stem + '*'))

        raise FileNotFoundError(
            'ncl_convert2nc completed, but did not create the expected file\n'
            f'executable: {exe}\n'
            f'command: {cmd}\n'
            f'expected output: {output_file}\n'
            f'output directory: {output_dir}\n'
            f'similar netCDF files: {similar_files}\n'
            f'nearby files: {nearby_files}\n'
            f'stdout:\n{result.stdout}\n'
            f'stderr:\n{result.stderr}'
        )

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

        for alt_i in range(ds.sizes[alt_dim]):
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
    near-surface variables such as temperature, dew point, humidity, wind components, and precipitation,
    adds descriptive metadata, computes derived wind speed fields, and writes the results to a new
    netCDF file in the same directory.

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

        # Convert GRIB to netCDF
        ncfile_full = grib2nc(grib_file, verbose=verbose)

        # Rename the netCDF file, then extract selected vars to the final netCDF file
        ncfile_tmp = ncfile_full.with_name(ncfile_full.name + '.tmp')
        ncfile_full.replace(ncfile_tmp)

        nc2nc_extract_vars(
            ncfile_tmp,
            ncfile,
            VARIABLES,
            long_names=LONG_NAMES,
            global_attributes=GLOBAL_ATTRS,
        )

        nc2nc_process_wind_speed(ncfile)

        ncfile_tmp.unlink()

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

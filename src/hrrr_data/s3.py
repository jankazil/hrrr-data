'''
Tools for operations on HRRR data in GRIB and Zarr formats on S3
(Amazon Simple Storage System).

S3 does not have a true directory structure.

Each object in S3 is stored as a key-object pair, where:

The key is a unique string that identifies the object (like a file path).

GRIB paths are relative to the NOAA HRRR bucket. The traditional HRRR Zarr
archive is stored in the separate hrrrzarr bucket.
'''

import hashlib
import json
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from itertools import product
from math import ceil
from pathlib import Path

import numpy as np
import s3fs
import xarray as xr

BUCKET = 'noaa-hrrr-bdp-pds'

_ZARR_BUCKET = 'hrrrzarr'
_ZARR_FORECAST_START = datetime(2018, 7, 12, 18)
_ZARR_GRID_PATH = 'grid/HRRR_chunk_index.zarr'
_ZARR_FORECAST_COORDINATE_GROUP = '2m_above_ground/TMP'

# Map output field names to their array paths in a forecast Zarr store.
_ZARR_SURFACE_FIELD_PATHS = {
    'TMP_P0_L103_GLC0': '2m_above_ground/TMP/2m_above_ground/TMP',
    'DPT_P0_L103_GLC0': '2m_above_ground/DPT/2m_above_ground/DPT',
    'U10': '10m_above_ground/UGRD/10m_above_ground/UGRD',
    'V10': '10m_above_ground/VGRD/10m_above_ground/VGRD',
    'APCP_P8_L1_GLC0_acc1h': 'surface/APCP_1hr_acc_fcst/surface/APCP_1hr_acc_fcst',
}


def grib_surface_forecast_files_exist(
    start_date: datetime,
    end_date: datetime,
    init_hour: int,
    forecast_lead_hour: int,
    region: str,
) -> bool:
    '''
    Check whether all specified HRRR surface GRIB2 files exist on S3.

    The date range is inclusive. The objects are in the NOAA HRRR bucket.
    S3 access errors propagate to the caller instead of being reported as missing
    files.

    Parameters
    ----------
    start_date : datetime
        First forecast initialization date to check.
    end_date : datetime
        Last forecast initialization date to check, inclusive.
    init_hour : int
        Forecast initialization hour in UTC, from 0 through 23.
    forecast_lead_hour : int
        Nonnegative forecast lead time in hours.
    region : str
        HRRR region identifier used in the S3 key, for example ``'conus'``.

    Returns
    -------
    bool
        True if every requested GRIB2 object exists; False if any is absent.

    Raises
    ------
    ValueError
        If the date range or hour arguments are invalid.
    '''
    if start_date > end_date:
        raise ValueError('Start date must be earlier than or equal to end date')
    if not 0 <= init_hour <= 23:
        raise ValueError('Forecast initialization hour must be between 0 and 23')
    if forecast_lead_hour < 0:
        raise ValueError('Forecast lead hour must be nonnegative')

    fs = s3fs.S3FileSystem(anon=True)
    date = start_date
    while date <= end_date:
        key = (
            f'hrrr.{date:%Y%m%d}/{region}/'
            f'hrrr.t{init_hour:02d}z.wrfsfcf{forecast_lead_hour:02d}.grib2'
        )
        if not fs.exists(f'{BUCKET}/{key}'):
            return False
        date += timedelta(days=1)

    return True


def zarr_surface_forecast_files_exist(
    start_date: datetime,
    end_date: datetime,
    init_hour: int,
    first_forecast_lead_hour: int,
    last_forecast_lead_hour: int,
    region: str,
) -> bool:
    '''
    Check whether specified HRRR surface forecast Zarr objects exist on S3.

    Check each forecast store, its requested lead hours, the chunks for the
    surface fields defined in ``_ZARR_SURFACE_FIELD_PATHS``, and the static grid
    coordinates. These objects reside in the separate ``hrrrzarr`` bucket.
    Missing S3 objects return False; other S3 access errors propagate.

    Parameters
    ----------
    start_date : datetime
        First forecast initialization date to check.
    end_date : datetime
        Last forecast initialization date to check, inclusive.
    init_hour : int
        Forecast initialization hour in UTC, from 0 through 23.
    first_forecast_lead_hour : int
        First requested forecast lead hour, inclusive; must be at least 1.
    last_forecast_lead_hour : int
        Last requested forecast lead hour, inclusive.
    region : str
        Geographic region identifier; only ``'conus'`` is supported.

    Returns
    -------
    bool
        True if every required source object exists and every requested lead
        hour is present in each forecast store; False otherwise.

    Raises
    ------
    ValueError
        If the dates, initialization hour, lead-hour range, or region is invalid.
    '''
    validate_zarr_forecast_request(
        start_date,
        end_date,
        init_hour,
        first_forecast_lead_hour,
        last_forecast_lead_hour,
        region,
        None,
    )
    fs = s3fs.S3FileSystem(anon=True)
    grid_url = f's3://{_ZARR_BUCKET}/{_ZARR_GRID_PATH}'
    coordinate_group = _ZARR_FORECAST_COORDINATE_GROUP
    variable_paths = set(_ZARR_SURFACE_FIELD_PATHS.values())
    groups = {coordinate_group} | {path.rpartition('/')[0] for path in variable_paths}
    grid_checked = False
    date = start_date

    while date <= end_date:
        store_url = f's3://{_ZARR_BUCKET}/{_zarr_forecast_path(date, init_hour)}'
        if not fs.exists(f'{store_url}/.zmetadata'):
            return False

        store_metadata = json.loads(fs.cat(f'{store_url}/.zmetadata'))['metadata']
        if f'{coordinate_group}/forecast_period/.zarray' not in store_metadata:
            return False
        store = s3fs.S3Map(root=store_url, s3=fs, check=False)
        with xr.open_zarr(
            store,
            group=coordinate_group,
            consolidated=True,
            chunks=None,
            decode_times=False,
            mask_and_scale=False,
        ) as ds:
            if 'forecast_period' not in ds:
                return False
            periods = np.asarray(ds['forecast_period'].values, dtype=np.int64)

        period_to_index = {int(hour): index for index, hour in enumerate(periods)}
        indices = [
            period_to_index.get(hour)
            for hour in range(first_forecast_lead_hour, last_forecast_lead_hour + 1)
        ]
        if None in indices or indices != list(range(indices[0], indices[-1] + 1)):
            return False

        # Include the arrays in the coordinate group as well as the selected
        # fields. Each forecast field uses time as its first chunk dimension.
        sources = [(store_url, variable_paths | {f'{coordinate_group}/forecast_period'})]
        if not grid_checked:
            sources.append((grid_url, {'latitude', 'longitude'}))

        for url, required_paths in sources:
            metadata_url = f'{url}/.zmetadata'
            if not fs.exists(metadata_url):
                return False
            metadata = (
                store_metadata if url == store_url else json.loads(fs.cat(metadata_url))['metadata']
            )
            array_paths = {
                key.removesuffix('/.zarray') for key in metadata if key.endswith('/.zarray')
            }
            if not required_paths <= array_paths:
                return False

            if url == grid_url:
                selected_paths = {path for path in array_paths if '/' not in path}
            else:
                selected_paths = {path for path in array_paths if path.rpartition('/')[0] in groups}

            for path in selected_paths:
                array_metadata = metadata[f'{path}/.zarray']
                if isinstance(array_metadata, str):
                    array_metadata = json.loads(array_metadata)
                shape = array_metadata['shape']
                chunks = array_metadata['chunks']
                chunk_ranges = [
                    range(ceil(length / size)) for length, size in zip(shape, chunks, strict=True)
                ]
                if url == store_url and path in variable_paths:
                    if max(indices) >= shape[0]:
                        return False
                    chunk_ranges[0] = sorted({index // chunks[0] for index in indices})

                separator = array_metadata.get('dimension_separator', '.')
                array_root = f'{url}/{path}'
                try:
                    listed = (
                        fs.find(array_root) if separator == '/' else fs.ls(array_root, detail=False)
                    )
                except FileNotFoundError:
                    return False
                root = array_root.removeprefix('s3://') + '/'
                available = {key.removeprefix('s3://').removeprefix(root) for key in listed}
                expected = {
                    separator.join(map(str, index)) if index else '0'
                    for index in product(*chunk_ranges)
                }
                if not expected <= available:
                    return False

            if url == grid_url:
                grid_checked = True

        date += timedelta(days=1)

    return True


def validate_zarr_forecast_request(
    start_date: datetime,
    end_date: datetime,
    init_hour: int,
    first_forecast_lead_hour: int,
    last_forecast_lead_hour: int,
    region: str,
    n_jobs: int | None,
) -> None:
    '''Validate a request for data from the traditional HRRR Zarr archive.'''

    if start_date > end_date:
        raise ValueError('Start date must be earlier than or equal to end date')
    if init_hour < 0 or init_hour > 23:
        raise ValueError('Forecast initialization hour must be between 0 and 23')
    if first_forecast_lead_hour < 1:
        raise ValueError(
            'First forecast lead hour must be at least 1. Forecast hour 0 is '
            'stored separately as an analysis and is not supported.'
        )
    if last_forecast_lead_hour < first_forecast_lead_hour:
        raise ValueError(
            'Last forecast lead hour must be greater than or equal to first forecast lead hour'
        )
    if region.lower() != 'conus':
        raise ValueError("The traditional HRRR Zarr forecast archive supports only region 'conus'")
    if n_jobs is not None and n_jobs < 1:
        raise ValueError('Number of parallel jobs must be at least 1')

    first_initialization = datetime(start_date.year, start_date.month, start_date.day, init_hour)
    if first_initialization < _ZARR_FORECAST_START:
        raise ValueError(
            'The traditional HRRR Zarr forecast archive begins at '
            f'{_ZARR_FORECAST_START:%Y-%m-%d %H} UTC'
        )


def zarr_forecast_store(date: datetime, init_hour: int) -> tuple[s3fs.S3Map, str]:
    '''Open one traditional HRRR forecast Zarr store for anonymous access.'''

    zarr_path = _zarr_forecast_path(date, init_hour)
    zarr_url = 's3://' + _ZARR_BUCKET + '/' + zarr_path
    fs = s3fs.S3FileSystem(anon=True)

    if not fs.exists(zarr_url + '/.zmetadata'):
        raise FileNotFoundError('HRRR Zarr forecast store is unavailable: ' + zarr_url)

    return s3fs.S3Map(root=zarr_url, s3=fs, check=False), zarr_url


def zarr_grid_store() -> s3fs.S3Map:
    '''Open the static HRRR CONUS latitude and longitude Zarr store.'''

    grid_url = 's3://' + _ZARR_BUCKET + '/' + _ZARR_GRID_PATH
    fs = s3fs.S3FileSystem(anon=True)
    return s3fs.S3Map(root=grid_url, s3=fs, check=False)


def _zarr_forecast_path(date: datetime, init_hour: int) -> str:
    '''Construct the S3 path of one traditional HRRR forecast Zarr store.'''

    date_string = date.strftime('%Y%m%d')
    return 'sfc/' + date_string + '/' + date_string + '_' + str(init_hour).zfill(2) + 'z_fcst.zarr'


def ls(path: str) -> list[str]:
    '''
    List the contents of an S3 path.

    Args:
        path (str): Path in the S3 HRRR bucket.

            Example paths:
                ''
                'hrrr.20201203/conus'

    Returns:
        list: List of path contents.
    '''

    # Access S3
    fs = s3fs.S3FileSystem(anon=True)

    # List files
    files = fs.ls(BUCKET + '/' + path)

    # Cut the bucket part from the path
    prefix = BUCKET + '/'

    paths = [file[len(prefix) :] for file in files if file.startswith(prefix)]

    return paths


def ls_re(path: str) -> list[str]:
    '''
    List the contents of an S3 path, allowing wildcards.

    Args:
        path (str): Path in the S3 HRRR bucket. May contain wildcards (regular expressions).

            Example paths:
                '*'
                'hrrr.20201203/conus/*'
                'hrrr.2025*/conus/*'

    Returns:
        list: List of path contents.
    '''

    # Access S3
    fs = s3fs.S3FileSystem(anon=True)

    # List files
    if path == '':
        files = fs.ls(BUCKET)
    else:
        files = fs.glob(BUCKET + '/' + path)

    # Cut the bucket part from the path
    prefix = BUCKET + '/'

    paths = [file[len(prefix) :] for file in files if file.startswith(prefix)]

    return paths


def download(hrrr_file: str, local_dir: Path, refresh: bool = False, verbose: bool = False) -> Path:
    '''
    Download a HRRR data file from S3, unless it already exists in the local directory.

    Args:
        hrrr_file (str): Path of the HRRR data file in the HRRR bucket (S3 key).
        local_dir (Path): Local directory where the file will be downloaded. Created if it does not exist.
        refresh (bool, optional): If True, download even if the file already exists. Defaults to False.
        verbose (bool, optional): If True, print detailed progress information to stdout. Defaults to False.

    Returns:
        Path: Local path of the downloaded file.
    '''

    # Create local directory unless it exists
    path = Path(local_dir)
    path.mkdir(parents=True, exist_ok=True)

    # Local file path
    local_file = Path(local_dir) / hrrr_file  # Path will normalize separators for the OS

    # Get the ETag of the object from S3 (remove surrounding double quotes)
    ETag = info(hrrr_file)['ETag'].strip('"')

    # Check if file already exists and is the same as the file in S3
    if not refresh and local_file.exists():
        # Compare the MD5 hash with its ETag from S3
        checksum = md5sum(local_file)

        if ETag == checksum:
            if verbose:
                print(
                    BUCKET + '/' + hrrr_file,
                    'already available locally as ',
                    str(local_file),
                    '. Skipping download.',
                    flush=True,
                )
            return local_file

    if verbose:
        print('Downloading from the NOAA HRRR S3 archive the file', local_file, flush=True)

    # Download the file from S3
    fs = s3fs.S3FileSystem(anon=True)
    fs.get(BUCKET + '/' + hrrr_file, str(local_file))

    # Check if the downloaded file matches the file in S3
    checksum = md5sum(local_file)

    if ETag != checksum:
        message = (
            'Download may have failed: ETag of local file '
            + str(local_file)
            + ' does not match ETag of S3 file '
            + BUCKET
            + '/'
            + hrrr_file
        )
        warnings.warn(message, stacklevel=2)
        # raise Exception(message)

    return local_file


def download_threaded(
    hrrr_files: list[str],
    local_dir: Path,
    refresh: bool = False,
    n_jobs: int = 1,
    verbose: bool = False,
) -> Path:
    '''
     Download a list of HRRR data file from S3, except those that already exists in the local directory,
     in parallel.

    Args:
        hrrr_file (list[str]): List of paths of the HRRR data file in the HRRR bucket (S3 key).
        local_dir (Path): Local directory where the file will be downloaded. Created if it does not exist.
        refresh (bool, optional): If True, download even if the file already exists. Defaults to False.
        n_jobs (int, optional): Maximum number of parallel downloads. Defaults to 1.
        verbose (bool, optional): If True, print detailed progress information to stdout. Defaults to False.
    Returns:
        list[str]: List of local paths of the downloaded files.
    '''

    if n_jobs is None:
        n_jobs = 1

    local_files = []

    with ThreadPoolExecutor(max_workers=n_jobs) as executor:
        futures = [
            executor.submit(download, hrrr_file, local_dir, refresh, verbose)
            for hrrr_file in hrrr_files
        ]
        for future in as_completed(futures):
            try:
                local_file = future.result()
                local_files.append(local_file)
            except Exception as exc:
                print(f"Download generated an exception: {exc}", flush=True)

    return local_files


def download_date_range(
    start_date: datetime,
    end_date: datetime,
    region: str,
    init_hour: int,
    forecast_lead_hour: int,
    data_type: str,
    local_dir: Path,
    refresh: bool = False,
    n_jobs: int = 1,
    verbose: bool = False,
) -> list[Path]:
    '''
    Downloads HRRR data files from S3 starting between (inclusive) given start and end dates,
    in parallel

    Args:
        start_date (datetime): The date of the first data file
        end_data (datetime): The date of the last data file
        region (str): One of 'alaska','conus'
        init_hour (int): Simulation initialization hour (UTC)
        forecast_lead_hour (int): Forecast lead time in hours
        data_type (str): A string specifying the data type in NOWW S3 HRRR data file name, e.g. 'wrfsfc'.
        local_dir (Path): Local directory where the files will be downloaded. Created if it does not exist.
        refresh (bool, optional): If True, download even if the file already exists. Defaults to False.
        n_jobs (int, optional): Maximum number of parallel downloads, Defaults to 1.
        verbose (bool, optional): If True, print detailed progress information to stdout. Defaults to False.

    Returns:
        list[Path]: List of local paths of the downloaded files.
    '''

    # Construct the paths (S3 keys) of the data files

    hrrr_files = []

    date = start_date

    while date <= end_date:
        hrrr_file = 'hrrr.'
        hrrr_file = hrrr_file + str(date.year) + str(date.month).zfill(2) + str(date.day).zfill(2)
        hrrr_file = hrrr_file + '/'
        hrrr_file = hrrr_file + region
        hrrr_file = hrrr_file + '/'
        hrrr_file = hrrr_file + 'hrrr.t'
        hrrr_file = hrrr_file + str(init_hour).zfill(2)
        hrrr_file = hrrr_file + 'z.'
        hrrr_file = hrrr_file + data_type
        hrrr_file = hrrr_file + 'f'
        hrrr_file = hrrr_file + str(forecast_lead_hour).zfill(2)
        hrrr_file = hrrr_file + '.grib2'

        hrrr_files.append(hrrr_file)

        date += timedelta(days=1)

    # Download files

    local_files = []

    local_files = download_threaded(
        hrrr_files, local_dir, refresh=refresh, n_jobs=n_jobs, verbose=verbose
    )

    return local_files


def info(hrrr_file: str) -> dict:
    '''

    Retrieves properties of an object in the S3 HRRR bucket.

    Args:
        hrrr_file (str): Path of the HRRR data file in the HRRR bucket (S3 key).

    Returns:
        dict: Dictionary containing S3 object properties, as returned by
              `s3fs.S3FileSystem.info`. Includes fields like size, last_modified,
              ETag, and Metadata (user-defined metadata).

              The units of size are bytes, the time is given as UTC,
              at the time of writing this code.

    '''

    fs = s3fs.S3FileSystem(anon=True)
    info = fs.info(BUCKET + '/' + hrrr_file)

    return info


def md5sum(local_file: Path):
    '''Compute the MD5 hash of a file's contents.

    This function reads the file in binary mode and processes it in
    fixed-size chunks to compute the MD5 checksum efficiently, without
    loading the entire file into memory.

    Args:
        local_file (str): Path to a local file.

    Returns:
        str: Hexadecimal MD5 hash of the file contents.

    '''

    h = hashlib.md5()

    with open(local_file, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)

    return h.hexdigest()

"""
Tools for operations on HRRR data files (in GRIB format) on S3 (Amazon Simple Storage System).

S3 does not have a true directory structure.

Each object in S3 is stored as a key-object pair, where:

The key is a unique string that identifies the object (like a file path).

In this module, we refer to the "keys" as "paths", and they are relative to the NOAA HRRR bucket.
"""

import hashlib
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path

import s3fs

BUCKET = 'noaa-hrrr-bdp-pds'


def ls(path: str) -> list[str]:
    """
    List the contents of an S3 path.

    Args:
        path (str): Path in the S3 HRRR bucket.

            Example paths:
                ''
                'hrrr.20201203/conus'

    Returns:
        list: List of path contents.
    """

    # Access S3
    fs = s3fs.S3FileSystem(anon=True)

    # List files
    files = fs.ls(BUCKET + '/' + path)

    # Cut the bucket part from the path
    prefix = BUCKET + '/'

    paths = [file[len(prefix) :] for file in files if file.startswith(prefix)]

    return paths


def ls_re(path: str) -> list[str]:
    """
    List the contents of an S3 path, allowing wildcards.

    Args:
        path (str): Path in the S3 HRRR bucket. May contain wildcards (regular expressions).

            Example paths:
                '*'
                'hrrr.20201203/conus/*'
                'hrrr.2025*/conus/*'

    Returns:
        list: List of path contents.
    """

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
    """
    Download a HRRR data file from S3, unless it already exists in the local directory.

    Args:
        hrrr_file (str): Path of the HRRR data file in the HRRR bucket (S3 key).
        local_dir (Path): Local directory where the file will be downloaded. Created if it does not exist.
        refresh (bool, optional): If True, download even if the file already exists. Defaults to False.
        verbose (bool, optional): If True, print detailed progress information to stdout. Defaults to False.

    Returns:
        Path: Local path of the downloaded file.
    """

    if verbose:
        print('Downloading from the NOAA HRRR S3 archive the file', hrrr_file, flush=True)

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
    """
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
    """

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
                print(f"Download generated an exception: {exc}")

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
    """
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
    """

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
    """

    Retrieves properties of an object in the S3 HRRR bucket.

    Args:
        hrrr_file (str): Path of the HRRR data file in the HRRR bucket (S3 key).

    Returns:
        dict: Dictionary containing S3 object properties, as returned by
              `s3fs.S3FileSystem.info`. Includes fields like size, last_modified,
              ETag, and Metadata (user-defined metadata).

              The units of size are bytes, the time is given as UTC,
              at the time of writing this code.

    """

    fs = s3fs.S3FileSystem(anon=True)
    info = fs.info(BUCKET + '/' + hrrr_file)

    return info


def md5sum(local_file: Path):
    """Compute the MD5 hash of a file's contents.

    This function reads the file in binary mode and processes it in
    fixed-size chunks to compute the MD5 checksum efficiently, without
    loading the entire file into memory.

    Args:
        local_file (str): Path to a local file.

    Returns:
        str: Hexadecimal MD5 hash of the file contents.

    """

    h = hashlib.md5()

    with open(local_file, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)

    return h.hexdigest()

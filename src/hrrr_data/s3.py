import s3fs
import xarray as xr
from pathlib import Path
import pygrib
import subprocess

"""
Tools for operations on HRRR data files (in GRIB format) on S3 (Amazon Simple Storage System).

S3 does not have a true directory structure.

Each object in S3 is stored as a key-object pair, where:

The key is a unique string that identifies the object (like a file path).

In this module, we refer to the "keys" as "paths", and they are relative to the NOAA HRRR bucket.
"""

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

    paths = [file[len(prefix):] for file in files if file.startswith(prefix)]

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

    paths = [file[len(prefix):] for file in files if file.startswith(prefix)]

    return paths

def download(hrrr_file: str, local_dir: Path, refresh: bool = False) -> Path:
    
    """
    Download a HRRR data file from S3, unless it already exists in the local directory.

    Args:
        hrrr_file (str): Path of the HRRR data file in the HRRR bucket (S3 key).
        local_dir (Path): Local directory where the file will be downloaded. Created if it does not exist.
        refresh (bool, optional): If True, download even if the file already exists. Defaults to False.

    Returns:
        Path: Local path of the downloaded file.
    """

    # Create local directory unless it exists
    path = Path(local_dir)
    path.mkdir(parents=True, exist_ok=True)

    # Local file path
    local_file = Path(local_dir) / hrrr_file  # Path will normalize separators for the OS

    # Check if file already exists
    if not refresh and local_file.exists():
        return local_file

    # Download the file from S3
    fs = s3fs.S3FileSystem(anon=True)
    fs.get(BUCKET + '/' + hrrr_file, str(local_file))

    return local_file

def grib_list_vars(file:Path) -> dict[str,str]:
    
    """
    Returns variable names and their descriptive names as found in a GRIB file.
    
    Args:
        file (Path): Local file path to a GRIB file
        
    Returns:
        dict [str,str]: Dictionary of variable names and their descriptive names
    """
    
    vars = {} # A dictionary mapping the variables -> descriptive names
    
    with pygrib.open(str(file)) as grbs:
        # pygrib.open returns a file-like object (a pygrib.open instance),
        # which behaves as an iterator over the GRIB messages in the file.
        for grb in grbs:
            if grb.shortName not in vars:
                vars[grb.shortName] = grb.name
    
    return vars

def grib2nc(grib_file:Path):
    
    """
    Converts a file in GRIB format to a file in netCDF format.
    
    For simplicity, we use an external tool, ncl_convert2nc, which must be installed on the host system.
    
    If the file in netCDF format exists, it will be overwritten.
    
    Args:
        grib_file (Path): Local file path to a file in GRIB format.
        
    Returns:
        Path: Local file path to a file in netCDF format.
    """
    
    # Construct the command
    
    output_dir = grib_file.parent
    output_file_name = grib_file.stem + '.nc'
    output_file = output_dir / output_file_name
    
    cmd = [
    'ncl_convert2nc',
    str(grib_file),
    '-o', output_dir
    ]
    
    # Call the command
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    # Print output
    print()
    print('running ncl_convert2nc to produce the file')
    print()
    print(str(output_file))
    print()
    if (result.stdout != ''):
        print(result.stdout)
    if (result.stderr != ''):
        print(result.stderr)
    
    return output_file
    
    

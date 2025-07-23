import s3fs
import xarray as xr

'''
Tools for operations on HRRR data files (in GRIB format) on S3 (Amazon Simple Storage System).

  S3 does not have a true directory structure.
  
  Each object in S3 is stored as a key-object pair, where:
  
  The key is a unique string that identifies the object (like a file path).
  
In this module, we refer to the "keys" as "paths", and they are relative to the NOAA HRRR bucket.
'''

BUCKET = 'noaa-hrrr-bdp-pds'

def ls(path:str) -> list[str]:
  
  '''
  
  List the contents of a S3 path.
  
  Args:
        path : Path in the S3 HRRR bucket.
        
               Example paths are
                 
                  ''
                  'hrrr.20201203/conus'
  
  '''
  
  # Access S3
  
  fs = s3fs.S3FileSystem(anon=True)
  
  # List files
  
  files = fs.ls(BUCKET + '/' + path)
  
  # Cut the bucket part from the path
  
  prefix = BUCKET + '/'
  
  paths = [file[len(prefix):] for file in files if file.startswith(prefix)]
  
  return paths

def ls_re(path:str) -> list[str]:
  
  '''
  
  List the contents of a S3 path, allow wildcards.
  
  Args:
        path : Path in the S3 HRRR bucket. May contain wildcards (regular expressions).
        
               Example paths are
                 
                  '*'
                  'hrrr.20201203/conus/*'
                  'hrrr.2025*/conus/*'
  
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
  
  paths = [file[len(prefix):] for file in files if file.startswith(prefix)]
  
  return paths

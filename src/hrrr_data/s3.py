import s3fs
import xarray as xr

'''
Tools for operations on HRRR data files (in GRIB format) on S3 (Amazon Simple Storage System).
'''

BUCKET = 'noaa-hrrr-bdp-pds'

def ls(path:str):
  
  '''
  
  List the contents of a S3 "directory".
  
  Args:
        path (str): The path ("key") in the S3 HRRR bucket. May contain wildcards (regular expressions).
        
                    An example path (key) is 'hrrr.20201203/conus/*'.
  
  '''
  
  fs = s3fs.S3FileSystem(anon=True)
  
  files = fs.glob(BUCKET + '/' + path)
  
  return files

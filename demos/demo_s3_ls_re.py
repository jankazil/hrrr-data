"""
List all objects in the S3 HRRR bucket that match a given regular expression and print their keys.
"""

from hrrr_data import s3

files = s3.ls_re('hrrr.20201203/conus/*sfc*')

for file in files:
    print(file)

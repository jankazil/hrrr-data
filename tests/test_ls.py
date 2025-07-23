"""
List all top-level objects in the S3 HRRR bucket and print their keys.
"""

from hrrr_data import s3

files = s3.ls('*')

for file in files:
  print(file)


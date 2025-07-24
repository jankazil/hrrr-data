from pathlib import Path
import pygrib
import subprocess

"""
Tools for operations on files in GRIB and netCDF format.
"""

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
    
    

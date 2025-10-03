#!/usr/bin/env python3
"""
Extract selected meteorological surface variables from a local HRRR GRIB2 file
and save them into a new netCDF file.

This CLI:
  - accepts a single GRIB2 file path as input
  - extracts a predefined set of surface variables
  - writes the extracted variables and associated metadata to a new netCDF file
    and removes the intermediate netCDF file created during conversion
"""

import argparse
import sys
from pathlib import Path

from hrrr_data import tools

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


def build_arg_parser() -> argparse.ArgumentParser:
    """Create an argument parser for the CLI."""
    parser = argparse.ArgumentParser(
        prog="hrrr-extract-sfc-vars",
        description=(
            "Extract from a local HRRR GRIB2 a predefined set of surface variables "
            "(temperature, humidity, wind, precipitation) and save them in a new netCDF file."
        ),
    )
    parser.add_argument(
        "grib_file",
        type=str,
        help="Path to GRIB2 file from which a netCDF file with select surface variables will be constructed.",
    )
    return parser


def extract_to_netcdf(grib_file: Path) -> Path:
    """Convert GRIB2 to netCDF and extract selected surface variables into a new file.

    Returns the path to the netCDF with selected surface variables.
    """
    ncfile = tools.grib2nc(grib_file)
    ncfile_select_vars_name = f"{ncfile.stem}_select_vars.nc"
    ncfile_select_vars = ncfile.parent / ncfile_select_vars_name
    tools.nc2nc_extract_vars(
        ncfile,
        ncfile_select_vars,
        VARIABLES,
        long_names=LONG_NAMES,
        global_attributes=GLOBAL_ATTRS,
    )
    ncfile.unlink()
    return ncfile_select_vars


def main(argv=None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    grib_path = Path(args.grib_file)

    if not grib_path.exists():
        parser.error(f"GRIB2 file does not exist: {grib_path}")

    out_file = extract_to_netcdf(grib_path)
    print(f"Extracted select surface variables from {grib_path} to {out_file}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

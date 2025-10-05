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


def main(argv=None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    grib_path = Path(args.grib_file)

    if not grib_path.exists():
        parser.error(f"GRIB2 file does not exist: {grib_path}")

    out_file = tools.extract_select_sfc_vars_to_netcdf(grib_path)
    print(f"Extracted select surface variables from {grib_path} to {out_file}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

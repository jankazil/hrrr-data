#!/usr/bin/env python3
"""
Create CONUS maps for all single-level HRRR variables in a netCDF file.

This command line interface (CLI):
  - accepts one path to a netCDF HRRR forecast file
  - identifies data variables whose dimensions are exactly ('ygrid_0', 'xgrid_0')
  - for each such variable, calls hrrr_data.plotting.plot_geographic to render a
    Lambert Conformal Conic map over CONUS and saves a PNG next to the input file
    named '<input>.<variable>.png'
  - derives the colorbar label from the variable attributes 'long_name' and 'units'

Notes:
  - Assumes that the netCDF file contains variables over CONUS.
"""

import argparse
import sys
from pathlib import Path

import xarray as xr

from hrrr_data import plotting


def build_arg_parser() -> argparse.ArgumentParser:
    """Create an argument parser for the CLI."""
    parser = argparse.ArgumentParser(
        prog="hrrr_plot_singlelevel_conus",
        description=(
            "Creates a plot of every HRRR variable in the given netCDF file that has only the "
            "horizontal grid dimensions ('ygrid_0', 'xgrid_0'), one PNG file per variable. "
            "Assumes that the netCDF file contains variables over CONUS."
        ),
    )
    parser.add_argument(
        "ncfile",
        type=str,
        help="Path to the netCDF HRRR forecast file.",
    )
    return parser


def main(argv=None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    ncfile = Path(args.ncfile)

    if not ncfile.exists():
        parser.error(f"netCDF file does not exist: {ncfile}")

    # Open the file
    ds = xr.open_dataset(ncfile)

    # Horizontal dimensions
    dims = ('ygrid_0', 'xgrid_0')

    # Select variables whose dimensions are the horizontal dimensions
    variables = [var for var in ds.data_vars if ds[var].dims == dims]

    # Plot each of these variables
    for var in variables:
        plot_path = ncfile.with_suffix('.' + var + '.png')

        plotting.plot_geographic(
            ds,
            var,
            cbar_label=ds[var].attrs['long_name'] + ' (' + ds[var].attrs['units'] + ')',
            cmap='coolwarm',
            plot_path=plot_path,
        )

        print('Created the plot', plot_path, flush=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

#!/usr/bin/env python3
"""
Download HRRR surface forecast data from the NOAA S3 bucket for a specified date range,
filter by forecast initialization and valid hour, and extract selected surface variables
into netCDF files.
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from hrrr_data import s3, tools


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hrrr-fetch-sfc-forecast",
        description=(
            "Download HRRR surface forecast data from the NOAA S3 bucket for a specified date range, "
            "for a specified forecast initialization and valid hour, and region; and if requested "
            "extract select surface variables into netCDF files. Both original GRIB2 files and "
            "processed netCDF files are saved in the given directory."
        ),
    )
    parser.add_argument("start_year", type=int, help="Start year of time range.")
    parser.add_argument("start_month", type=int, help="Start month of time range.")
    parser.add_argument("start_day", type=int, help="Start day of time range.")
    parser.add_argument("end_year", type=int, help="End year of time range.")
    parser.add_argument("end_month", type=int, help="End month of time range.")
    parser.add_argument("end_day", type=int, help="End day of time range.")
    parser.add_argument(
        "forecast_init_hour",
        type=int,
        help="Forecast initialization hour (see HRRR documentation for availability).",
    )
    parser.add_argument(
        "forecast_valid_hour",
        type=int,
        help="Forecast valid hour (see HRRR documentation for availability).",
    )
    parser.add_argument(
        "region",
        type=str,
        help="Region (e.g., conus). See HRRR documentation for valid options.",
    )
    parser.add_argument(
        "data_dir",
        type=str,
        help="Directory into which the data will be downloaded. Created if it does not exist.",
    )
    parser.add_argument(
        "-n",
        "--n",
        dest="n_jobs",
        type=int,
        default=None,
        help="Number of parallel download processes.",
    )
    parser.add_argument(
        "-e",
        "--extract",
        action='store_true',
        help="Extract select variables from downloaded GRIB2 files to netCDF files.",
    )
    return parser


def main(argv=None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    start_date = datetime(year=args.start_year, month=args.start_month, day=args.start_day)
    end_date = datetime(year=args.end_year, month=args.end_month, day=args.end_day)
    init_hour = args.forecast_init_hour
    forecast_hour = args.forecast_valid_hour
    region = args.region
    local_dir = Path(args.data_dir)
    n_jobs: int | None = args.n_jobs
    extract: Optional = args.extract

    data_type = "wrfsfc"  # Surface data

    grib_files = s3.download_date_range(
        start_date, end_date, region, init_hour, forecast_hour, data_type, local_dir, n_jobs=n_jobs
    )

    if extract:
        for grib_file in grib_files:
            out_file = tools.extract_select_sfc_vars_to_netcdf(grib_file)
            if out_file:
                print(
                    f"Extracted select surface variables from {grib_file} to {out_file}", flush=True
                )

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

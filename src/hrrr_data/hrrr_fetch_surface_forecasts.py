#!/usr/bin/env python3
"""
This script automates the retrieval and optional postprocessing of HRRR (High-Resolution Rapid Refresh)
surface forecast data from the NOAA AWS S3 archive. It allows users to specify a date range, initialization
hour, forecast lead hour, and target region to download the corresponding HRRR surface forecast GRIB2 files.
If requested, it extracts selected surface variables from the GRIB2 files and saves them as netCDF files.
The script can be executed as a command-line tool or imported as a module for programmatic use.
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from hrrr_data import s3, tools


def run_fetch(
    start_date: datetime,
    end_date: datetime,
    init_hour: int,
    forecast_lead_hour: int,
    region: str,
    local_dir: Path,
    n_jobs: int,
    extract: bool = True,
    verbose: bool = False,
) -> list[Path]:
    """
    Download HRRR surface forecast GRIB2 files for a given date range and configuration, and optionally
    extract selected surface variables into netCDF files.

    Parameters
    ----------
    start_date : datetime
        The starting date of the forecast period to download.
    end_date : datetime
        The ending date of the forecast period to download.
    init_hour : int
        The forecast initialization hour (UTC) for which HRRR runs will be downloaded.
    forecast_lead_hour : int
        The forecast lead time in hours to select the forecast output.
    region : str
        The geographic region identifier (for example, "conus").
    local_dir : Path
        Directory path where downloaded and processed files will be saved.
    n_jobs : int
        Number of parallel processes to use for downloading files.
    extract : bool, optional
        If True, extract select surface variables from each GRIB2 file into a netCDF file. Default is True.
    verbose : bool, optional
        If True, print progress and status messages. Default is False.

    Returns
    -------
    list[Path]
        A list of paths to the generated netCDF files if extraction is enabled, or an empty list otherwise.
    """

    data_type = "wrfsfc"  # Surface data

    refresh = False

    grib_files = s3.download_date_range(
        start_date,
        end_date,
        region,
        init_hour,
        forecast_lead_hour,
        data_type,
        local_dir,
        refresh=refresh,
        n_jobs=n_jobs,
        verbose=verbose,
    )

    out_files = []

    if extract:
        for grib_file in grib_files:
            out_file = tools.extract_select_sfc_vars_to_netcdf(grib_file, verbose=verbose)
            if out_file:
                out_files.append(out_file)
                if verbose:
                    print(
                        f"Extracted select surface variables from {grib_file} to {out_file}",
                        flush=True,
                    )

    return out_files


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hrrr-fetch-sfc-forecast",
        description=(
            "Download HRRR surface forecast data from the NOAA S3 bucket for a specified date range, "
            "for a specified forecast initialization hour and forecast lead hour, and region; and if requested "
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
        "forecast_lead_hour",
        type=int,
        help="Forecast lead time in hours (see HRRR documentation for availability).",
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
    parser.add_argument(
        "-v",
        "--verbose",
        action='store_true',
        help="Print detailed progress information.",
    )
    return parser


def main(argv=None) -> int:
    '''
    Command line interface entry point.
    '''

    parser = build_arg_parser()
    args = parser.parse_args(argv)

    start_date = datetime(year=args.start_year, month=args.start_month, day=args.start_day)
    end_date = datetime(year=args.end_year, month=args.end_month, day=args.end_day)
    init_hour = args.forecast_init_hour
    forecast_lead_hour = args.forecast_lead_hour
    region = args.region
    local_dir = Path(args.data_dir)
    n_jobs: int | None = args.n_jobs
    extract: Optional = args.extract
    verbose: Optional = args.verbose

    out_files = run_fetch(
        start_date,
        end_date,
        init_hour,
        forecast_lead_hour,
        region,
        local_dir,
        n_jobs,
        extract=extract,
        verbose=verbose,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

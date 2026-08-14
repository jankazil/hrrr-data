#!/usr/bin/env python3
'''
Download a range of HRRR (High-Resolution Rapid Refresh) surface forecast hours
from the public HRRR Zarr archive on AWS S3 and save one compatible netCDF file
per forecast hour.

The requested forecast-hour range is inclusive. Forecast hour 0 is not
supported because the traditional HRRR Zarr archive stores it separately as an
analysis; forecast stores contain forecast hours 1 onward. The Zarr archive
used by this script contains CONUS forecasts beginning with HRRR version 3 in
July 2018.

Only the selected surface variables are read from the remote Zarr store. No
local Zarr store is created. The resulting netCDF files use the variable names,
horizontal dimensions, coordinates, and metadata expected by the existing
HRRR plotting and analysis tools.
'''

from __future__ import annotations

import argparse
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path

from hrrr_data import s3, tools


def run_fetch(
    start_date: datetime,
    end_date: datetime,
    init_hour: int,
    first_forecast_lead_hour: int,
    last_forecast_lead_hour: int,
    region: str,
    local_dir: Path,
    n_jobs: int = 1,
    refresh: bool = False,
    verbose: bool = False,
) -> list[Path]:
    '''
    Download a range of HRRR surface forecast hours from Zarr and create one
    compatible netCDF file per forecast hour and model run.

    The forecast-hour range includes both ``first_forecast_lead_hour`` and
    ``last_forecast_lead_hour``. Forecast hour 0 is not supported because it is
    stored in a separate analysis Zarr store; this function reads only forecast
    stores, whose forecast periods begin at hour 1.

    Parameters
    ----------
    start_date : datetime
        The starting date of the forecast period to download.
    end_date : datetime
        The ending date of the forecast period to download.
    init_hour : int
        The forecast initialization hour (UTC) for which HRRR runs will be
        downloaded.
    first_forecast_lead_hour : int
        The first forecast lead hour to download, inclusive. Must be at least
        1; forecast hour 0 is not supported.
    last_forecast_lead_hour : int
        The last forecast lead hour to download, inclusive. It must be greater
        than or equal to ``first_forecast_lead_hour`` and available for every
        requested model run.
    region : str
        Geographic region identifier. The traditional HRRR Zarr forecast
        archive supports only ``'conus'``.
    local_dir : Path
        Directory path where generated netCDF files will be saved.
    n_jobs : int, optional
        Number of model runs to process in parallel. Default is 1. Increasing
        this value also increases memory use because each process reads one
        forecast cube at a time.
    refresh : bool, optional
        If True, recreate netCDF files even if they already exist. If False,
        existing netCDF files are retained. Default is False.
    verbose : bool, optional
        If True, print progress and status messages. Default is False.

    Returns
    -------
    list[Path]
        Paths to all requested netCDF files, including existing files retained
        when ``refresh`` is False.

    Raises
    ------
    ValueError
        If the dates, initialization hour, forecast-hour range, region, or
        number of parallel jobs are invalid.
    FileNotFoundError
        If a requested HRRR Zarr forecast store is unavailable.
    '''

    s3.validate_zarr_forecast_request(
        start_date,
        end_date,
        init_hour,
        first_forecast_lead_hour,
        last_forecast_lead_hour,
        region,
        n_jobs,
    )

    if n_jobs is None:
        n_jobs = 1
    region = region.lower()

    dates = []
    date = start_date
    while date <= end_date:
        dates.append(date)
        date += timedelta(days=1)

    output_files = []

    if n_jobs == 1:
        for date in dates:
            output_files.extend(
                tools.extract_select_sfc_zarr_vars_to_netcdf(
                    date,
                    init_hour,
                    first_forecast_lead_hour,
                    last_forecast_lead_hour,
                    region,
                    local_dir,
                    refresh=refresh,
                    verbose=verbose,
                )
            )
    else:
        with ProcessPoolExecutor(max_workers=n_jobs) as executor:
            futures = {
                executor.submit(
                    tools.extract_select_sfc_zarr_vars_to_netcdf,
                    date,
                    init_hour,
                    first_forecast_lead_hour,
                    last_forecast_lead_hour,
                    region,
                    local_dir,
                    refresh,
                    verbose,
                ): date
                for date in dates
            }

            for future in as_completed(futures):
                date = futures[future]
                try:
                    output_files.extend(future.result())
                except Exception as exc:
                    raise RuntimeError(
                        f'Processing the HRRR Zarr forecast initialized on '
                        f'{date:%Y-%m-%d} at {init_hour:02d} UTC failed'
                    ) from exc

    return sorted(output_files)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog='hrrr-fetch-sfc-forecast-zarr',
        description=(
            'Read an inclusive range of HRRR surface forecast hours from the traditional '
            'HRRR Zarr archive on AWS S3 and save one compatible netCDF file per forecast '
            'hour. Only CONUS forecasts from HRRR version 3 onward are available. Forecast '
            'hour 0 is not supported because it is stored separately as an analysis. No '
            'local Zarr store is created.'
        ),
    )
    parser.add_argument('start_year', type=int, help='Start year of time range.')
    parser.add_argument('start_month', type=int, help='Start month of time range.')
    parser.add_argument('start_day', type=int, help='Start day of time range.')
    parser.add_argument('end_year', type=int, help='End year of time range.')
    parser.add_argument('end_month', type=int, help='End month of time range.')
    parser.add_argument('end_day', type=int, help='End day of time range.')
    parser.add_argument(
        'forecast_init_hour',
        type=int,
        help='Forecast initialization hour in UTC, from 0 through 23.',
    )
    parser.add_argument(
        'first_forecast_lead_hour',
        type=int,
        help=(
            'First forecast lead hour to download, inclusive. Must be at least 1; '
            'forecast hour 0 is stored separately as an analysis and is not supported.'
        ),
    )
    parser.add_argument(
        'last_forecast_lead_hour',
        type=int,
        help=(
            'Last forecast lead hour to download, inclusive. It must be available for '
            'each requested model run.'
        ),
    )
    parser.add_argument(
        'region',
        type=str,
        help="Region. The traditional HRRR Zarr forecast archive supports only 'conus'.",
    )
    parser.add_argument(
        'data_dir',
        type=str,
        help=(
            'Directory into which the compatible netCDF files will be written. It is '
            'created if it does not exist. No local Zarr store is created.'
        ),
    )
    parser.add_argument(
        '-n',
        '--n',
        dest='n_jobs',
        type=int,
        default=None,
        help=(
            'Number of model runs to process in parallel. Higher values also increase memory use.'
        ),
    )
    parser.add_argument(
        '-r',
        '--refresh',
        action='store_true',
        help='Recreate requested netCDF files even if they already exist.',
    )
    parser.add_argument(
        '-v',
        '--verbose',
        action='store_true',
        help='Print detailed progress information.',
    )
    return parser


def main(argv=None) -> int:
    '''Command line interface entry point.'''

    parser = build_arg_parser()
    args = parser.parse_args(argv)

    try:
        start_date = datetime(year=args.start_year, month=args.start_month, day=args.start_day)
        end_date = datetime(year=args.end_year, month=args.end_month, day=args.end_day)
    except ValueError as exc:
        parser.error(str(exc))

    try:
        run_fetch(
            start_date,
            end_date,
            args.forecast_init_hour,
            args.first_forecast_lead_hour,
            args.last_forecast_lead_hour,
            args.region,
            Path(args.data_dir),
            n_jobs=args.n_jobs,
            refresh=args.refresh,
            verbose=args.verbose,
        )
    except ValueError as exc:
        parser.error(str(exc))

    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))

# Agent Development Guide

## Project Scope and Isolation

**The project root is the directory containing this `AGENTS.md` (`.` relative to
this file). That directory is the exclusive project boundary for every session.**

- Read, search, analyze, and modify only files contained within this root.
- Do not inspect parent directories, sibling projects, or other external locations,
  including external configuration files or installed dependency source code.
- Do not follow symbolic links or external Git references outside the root. Check
  destinations before using linked paths, worktree metadata, submodules, or Git
  object alternates; do not access an external destination.
- Base project-specific decisions on verified contents of this repository. Do not
  import assumptions from unrelated projects or previous development sessions.
- If an operation requires information or files outside the boundary, report that
  dependency instead of accessing it. Repository links and service URLs describe
  interfaces; they do not authorize external inspection or network access.
- Keep development inputs, outputs, fixtures, and temporary files inside the root.
  Review scripts for external effects before execution. The setup and publishing
  scripts described below require external resources and cannot be run unchanged
  under this isolation policy.

## Purpose and Repository Map

`hrrr-data` is a Python toolkit for retrieving NOAA High-Resolution Rapid Refresh
(HRRR) forecasts, extracting surface fields into netCDF, and plotting CONUS maps.
Use [README.md](README.md) for user workflows, CLI arguments, and file naming.

| Path | Responsibility |
| --- | --- |
| `src/hrrr_data/s3.py` | Anonymous S3 listing, metadata, downloads, availability checks, Zarr request validation and store lifecycle. |
| `src/hrrr_data/tools.py` | GRIB field selection, GRIB/Zarr-to-netCDF output, netCDF helpers, metadata and grid handling. |
| `src/hrrr_data/hrrr_fetch_surface_forecasts.py` | GRIB download orchestration and optional extraction; exposes `run_fetch`. |
| `src/hrrr_data/hrrr_fetch_surface_forecasts_zarr.py` | Inclusive Zarr forecast-range orchestration; exposes `run_fetch`. |
| `src/hrrr_data/hrrr_extract_surface_vars.py` | Local GRIB extraction CLI. |
| `src/hrrr_data/hrrr_plot_singlelevel_conus.py`, `plotting.py` | Per-variable PNG CLI and reusable Cartopy/Matplotlib plotting. |
| `src/hrrr_data/__init__.py` | Version from installed distribution metadata, with a local fallback. |
| `tests/test_test.py`, `src/hrrr_data/test.py` | Only an arithmetic placeholder test and its helper. |
| `demos/`, `plots/` | Usage examples and a README example image; no forecast data fixtures. |
| `pyproject.toml`, `environment.yml` | Packaging, CLI entry points, dependency declarations and tooling settings. |
| `Makefile`, `scripts/`, `.github/workflows/ci.yml` | Development commands, setup/release automation and CI. |

## Architecture and Data Contracts

- GRIB flow: fetch CLI → `s3.download_date_range` → threaded downloads → optional
  `tools.extract_select_sfc_vars_to_netcdf` → `grib2nc`. Extraction is sequential
  after downloading. Public GRIB helpers take keys relative to `s3.BUCKET`.
- Zarr flow: fetch CLI validates the request → processes each initialization date
  → reads selected remote fields and cached static grid coordinates → writes one
  netCDF per lead hour. With multiple jobs, `ProcessPoolExecutor` uses `spawn` to
  avoid inheriting S3 connections and event loops. No local Zarr store is created.
- Plotting reads netCDF and requires dimensions exactly `('ygrid_0', 'xgrid_0')`,
  coordinate fields `gridlat_0` and `gridlon_0`, and variable attributes including
  `long_name`, `units`, `initial_time` (`%m/%d/%Y (%H:%M)`),
  `forecast_time_units='hours'`, and integer-like `forecast_time`.
- Preserve compatible field names in both conversion paths:
  `TMP_P0_L103_GLC0`, `DPT_P0_L103_GLC0`, `U10`, `V10`, and
  `APCP_P8_L1_GLC0_acc1h`. These represent 2 m temperature/dewpoint, 10 m wind
  components, and 1-hour accumulated precipitation. GRIB extraction permits
  missing precipitation at lead hour 0; do not synthesize it.
- GRIB selectors use numerical parameter identifiers, level type and level;
  require exactly one matching message and a consistent horizontal grid.
  Keep Zarr field paths in `s3.py` aligned with field metadata in `tools.py`.
- Both conversion paths use float32 fields and coordinates, masked missing data,
  and `.nc.tmp` files followed by replacement. Preserve resource cleanup and
  temporary-file cleanup on errors; do not treat a forecast range as one atomic
  transaction or run concurrent writers against the same output paths.
- Date ranges are inclusive, and initialization hours are UTC. Output layout is
  `hrrr.YYYYMMDD/REGION/hrrr.tIIz.wrfsfcfFF.grib2` or `.nc` below the chosen
  data directory. Preserve refresh/skip behavior and existing file naming.
- Zarr validation supports CONUS only, initialization hours 0–23, ordered lead
  ranges beginning at 1, positive job counts, and initializations from
  2018-07-12 18 UTC. Requested periods must exist and be contiguous in each store.
  Hour 0 belongs to a separate analysis store and is unsupported by this path.
- `s3.download_threaded` prints worker errors and returns successful paths;
  a returned list does not prove all requested GRIB files downloaded. Download
  integrity currently compares local MD5 with S3 ETag and warns on mismatch.

## Environment, Configuration and External Interfaces

- Python requirement: **3.12+** (`pyproject.toml`, `environment.yml`). Packaging
  uses the `src/` layout, setuptools >=77, and wheel.
- Runtime dependencies declared in both manifests: Cartopy, Matplotlib, NumPy,
  netCDF4, pygrib, requests, s3fs, xarray, and zarr. Development extras declare
  pytest, pytest-cov, Ruff, and pre-commit. `environment.yml` uses conda-forge
  and also includes mamba and Jupyter tooling. Update both manifests when changing
  shared runtime dependencies.
- CI installs with `python -m pip install -e ".[dev]"`. This is a verified setup
  command, not permission to install or access external files under isolation.
- `make setup-dev-env` invokes `scripts/setup-dev-env.sh`: requires conda, prefers
  mamba, generates `environment-dev.yml`, removes/recreates `hrrr-data-dev`,
  replaces its user Jupyter kernel, installs editable code and pre-commit hooks.
  It affects locations outside this root; report this before attempting setup.
- Application configuration is through CLI arguments/function parameters and
  constants in `s3.py`; no application environment-variable interface was found.
- Source uses anonymous, read-only S3 access to `noaa-hrrr-bdp-pds` (GRIB) and
  `hrrrzarr` (Zarr). Forecast stores follow
  `sfc/YYYYMMDD/YYYYMMDD_IIz_fcst.zarr`; static coordinates come from
  `grid/HRRR_chunk_index.zarr`. Network access is an external dependency.
- Zarr access uses `FsspecStore`, an asynchronous s3fs filesystem with instance
  caching disabled, and consolidated metadata. Always close stores through
  `s3.close_zarr_store`, including failed reads; cleanup uses Zarr's event loop.
- `make upload-anaconda` runs a build-and-upload script, not a validation task.
  It requires conda and `ANACONDA_API_TOKEN`; optional overrides include
  `ANACONDA_USER_NAME`, `LICENSE_ID`, `PYPROJECT`, `IMPORT_NAME_OVERRIDE`,
  `BUILD_ENV_PREFIX`, and `BUILD_ENV_NAME`. It creates external temporary files
  and environments and publishes to Anaconda.org. Do not use it for routine checks.

## Conventions and Validation Commands

Follow nearby code: snake_case functions/modules, `Path` for filesystem paths,
annotations where established, documented public functions, and thin argparse
entry points with `build_arg_parser()`, `main(argv=None)`, and a `SystemExit` guard.
Console script mappings live in `[project.scripts]` in `pyproject.toml`.

`.editorconfig` specifies UTF-8, LF, a final newline, four-space indentation, and
two spaces for YAML/JSON/TOML. Ruff uses a 100-character line length and preserves
existing quote style. Enabled lint groups are E, F, I, UP, B, SIM with configured
exceptions; use the repository configuration rather than introducing a new style.

Run commands from the root with an available project environment. Check that tools,
fixtures, caches and temporary outputs comply with the boundary before execution.

| Command | Behavior |
| --- | --- |
| `python -m ruff check .` | Non-fixing lint command used by CI. |
| `python -m ruff format --check .` | Non-fixing counterpart of the configured formatter. |
| `pytest` or `make test` | Runs tests under `tests/`; CI also uses `pytest`. |
| `make fmt` | Reformats Python files. |
| `make lint` | Runs Ruff with `--fix`, modifying files. |
| `make check` | Runs both formatting and fixing lint; does not run tests. |

CI covers Python `3.12` and floating `3.x` on Ubuntu. Pre-commit configuration adds
YAML/JSON, final-newline and whitespace checks plus Ruff lint/format hooks.
There is no implemented `make type` or `make upload-pypi` target despite README
references, and no dedicated build-only Makefile target. Do not invent substitutes
or run release automation as a build check.

## Making and Reviewing Changes

1. Read the relevant implementation, README section and configuration before
   editing. Check the working tree and preserve unrelated changes.
2. Keep changes focused. Preserve CLI/API behavior and output schemas unless the
   task explicitly changes them; update README examples when behavior changes.
3. For behavior changes, add focused tests using synthetic data or mocked service
   access where practical. Useful cases include field selection, metadata/grid
   compatibility, invalid dates/leads, existing outputs, missing fields, cleanup,
   and worker failure behavior. Keep fixtures inside the root.
4. Run relevant checks when available and permitted. Inspect the final diff for
   unintended formatting, generated data, credentials, and files outside scope.
   `data`, build outputs and common Python caches are ignored by `.gitignore`;
   ignoring a file does not make it an appropriate source change.
5. Report behavior changed, checks actually run, and remaining verification gaps.
   Distinguish static inspection, mocked tests and real archive validation.

## Known Gaps and Manual Verification

- The sole existing test checks `add(2, 2) == 4`; it provides no evidence about
  downloads, conversion, plotting, Zarr behavior or scientific correctness.
- Dependency installation, native-library availability, live archive contents,
  plotting resources, and end-to-end output equivalence are not established by
  repository inspection. Verify these in an explicitly authorized environment.
- `zarr` is unpinned although source imports Zarr 3 APIs; s3fs/Zarr lifecycle code
  uses internal attributes/APIs. Verify version compatibility when changing them.
  Ruff targets `py310` even though runtime requires Python 3.12+; this is a
  configuration discrepancy, not support for Python 3.10.
- README variable lists and some extraction docstrings differ from current code
  (for example, references to relative humidity or derived wind speed). Inspect
  field dictionaries and implementations before relying on those descriptions.
- Demo scripts use `Path('..') / 'data' / 'HRRR'` relative to the process working
  directory and can access outside the root. Do not run them unchanged from the
  root; adapt paths within the authorized task or report the dependency.
- Increasing Zarr job count increases memory use. Real resource limits, archive
  availability and full integration behavior need manual verification; do not
  infer them from the placeholder suite.

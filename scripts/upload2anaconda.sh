#!/usr/bin/env bash

set -euo pipefail

# Build and upload a pure-Python conda package from the local working tree.
#
# The script may live in scripts/ and may be called from any working directory.
# It reads project metadata from pyproject.toml, writes a temporary conda recipe,
# builds the package in an isolated helper environment, and uploads the resulting
# artifact to anaconda.org.

# -----------------------------------------------------------------------------
# Defaults and global state
# -----------------------------------------------------------------------------

ANACONDA_USER_NAME="${ANACONDA_USER_NAME:-jan.kazil}"
LICENSE_ID="${LICENSE_ID:-BSD-3-Clause}"
PYPROJECT="${PYPROJECT:-pyproject.toml}"
IMPORT_NAME_OVERRIDE="${IMPORT_NAME_OVERRIDE:-}"
BUILD_ENV_PREFIX="${BUILD_ENV_PREFIX:-conda-build-upload-tmp}"
BUILD_ENV_NAME="${BUILD_ENV_NAME:-${BUILD_ENV_PREFIX}-${BASHPID}}"

ORIGINAL_PATH="$PATH"

SCRIPT_DIR=""
PROJECT_ROOT=""
PYTHON_FOR_METADATA=""
BASE_CONDA_PREFIX=""
BASE_CONDA_EXE=""
BUILD_ENV_DIR=""
ARTIFACT=""

BUILD_CROOT="$(mktemp -d "${TMPDIR:-/tmp}/conda-bld.XXXXXXXXXX")"
RECIPE_DIR="$(mktemp -d "${TMPDIR:-/tmp}/conda-recipe.XXXXXXXXXX")"
METADATA_FILE="$(mktemp "${TMPDIR:-/tmp}/conda-metadata.XXXXXXXXXX")"

# -----------------------------------------------------------------------------
# Generic helpers
# -----------------------------------------------------------------------------

die() {
    echo "Error: $*" >&2
    exit 1
}

cleanup() {
    local status=$?
    set +e

    if command -v conda >/dev/null 2>&1; then
        eval "$(conda shell.bash hook)" >/dev/null 2>&1 || true

        while [[ "${CONDA_SHLVL:-0}" -gt 0 ]]; do
            conda deactivate >/dev/null 2>&1 || break
        done

        conda env remove -n "$BUILD_ENV_NAME" -y >/dev/null 2>&1 || true
    fi

    rm -rf "$RECIPE_DIR"
    rm -rf "$BUILD_CROOT"
    rm -f "$METADATA_FILE"

    exit "$status"
}

trap cleanup EXIT INT TERM

print_pipe_list() {
    local items="$1"
    local old_ifs
    local item

    if [[ -n "$items" ]]; then
        old_ifs="$IFS"
        IFS='|'
        for item in $items; do
            [[ -n "$item" ]] && echo "  - $item"
        done
        IFS="$old_ifs"
    else
        echo "  (none)"
    fi
}

run_isolated() {
    env \
        -u PYTHONHOME \
        -u PYTHONPATH \
        PYTHONNOUSERSITE=1 \
        CONDA_EXE="$BASE_CONDA_EXE" \
        CONDA_PYTHON_EXE="$BASE_CONDA_PREFIX/bin/python" \
        PATH="$BASE_CONDA_PREFIX/bin:$ORIGINAL_PATH" \
        "$@"
}

# -----------------------------------------------------------------------------
# Project and tool discovery
# -----------------------------------------------------------------------------

resolve_script_dir() {
    local script_source
    local script_dir

    script_source="${BASH_SOURCE[0]}"
    while [[ -L "$script_source" ]]; do
        script_dir="$(cd -P "$(dirname "$script_source")" >/dev/null 2>&1 && pwd)"
        script_source="$(readlink "$script_source")"
        [[ "$script_source" != /* ]] && script_source="$script_dir/$script_source"
    done

    SCRIPT_DIR="$(cd -P "$(dirname "$script_source")" >/dev/null 2>&1 && pwd)"
}

enter_project_root() {
    if PROJECT_ROOT="$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel 2>/dev/null)"; then
        cd "$PROJECT_ROOT"
    else
        die "could not locate the Git project root from $SCRIPT_DIR."
    fi

    PROJECT_ROOT="$(pwd -P)"
}

require_project_inputs() {
    [[ -f "$PYPROJECT" ]] || die "could not find $PYPROJECT."
    command -v conda >/dev/null 2>&1 || die "conda is required on PATH."
}

find_base_conda() {
    BASE_CONDA_PREFIX="$(conda info --base)"
    BASE_CONDA_EXE="$BASE_CONDA_PREFIX/bin/conda"

    [[ -x "$BASE_CONDA_EXE" ]] || \
        die "expected base conda executable not found: $BASE_CONDA_EXE"
}

find_metadata_python() {
    if command -v python3 >/dev/null 2>&1; then
        PYTHON_FOR_METADATA="python3"
    elif command -v python >/dev/null 2>&1; then
        PYTHON_FOR_METADATA="python"
    else
        die "python or python3 is required on PATH to read $PYPROJECT."
    fi
}

# -----------------------------------------------------------------------------
# Recipe generation
# -----------------------------------------------------------------------------

# The embedded Python code reads pyproject.toml, maps selected PyPI-style
# requirements to conda package names, writes meta.yaml, and emits shell
# assignments that this Bash script sources afterward.
generate_recipe_and_metadata() {
    "$PYTHON_FOR_METADATA" - \
        "$PYPROJECT" \
        "$IMPORT_NAME_OVERRIDE" \
        "$LICENSE_ID" \
        "$RECIPE_DIR/meta.yaml" \
        "$PROJECT_ROOT" \
        "$BASE_CONDA_EXE" \
        > "$METADATA_FILE" <<'PY'
from __future__ import annotations

import json
import re
import shlex
import sys
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:
    print('Error: Python 3.11+ is required, or install tomli and modify this script to import it.', file=sys.stderr)
    raise SystemExit(1)

pyproject_path = Path(sys.argv[1])
import_name_override = sys.argv[2]
license_id = sys.argv[3]
meta_yaml_path = Path(sys.argv[4])
project_root = Path(sys.argv[5]).resolve()
base_conda_exe = sys.argv[6]

with pyproject_path.open('rb') as f:
    data = tomllib.load(f)

project = data.get('project', {})
build_system = data.get('build-system', {})

name = project.get('name')
version = project.get('version')
summary = project.get('description')
python_spec = project.get('requires-python')
raw_deps = project.get('dependencies', []) or []
raw_build_deps = build_system.get('requires', []) or ['setuptools>=77', 'wheel']

# -----------------------------------------------------------------------------
# Metadata validation
# -----------------------------------------------------------------------------

missing = [
    field
    for field, value in (
        ('project.name', name),
        ('project.version', version),
        ('project.description', summary),
        ('project.requires-python', python_spec),
    )
    if not value
]
if missing:
    print(f"Error: missing required metadata in {pyproject_path}: {', '.join(missing)}", file=sys.stderr)
    raise SystemExit(1)

if not isinstance(raw_deps, list) or not all(isinstance(dep, str) for dep in raw_deps):
    print('Error: project.dependencies must be a TOML list of strings.', file=sys.stderr)
    raise SystemExit(1)

if not isinstance(raw_build_deps, list) or not all(isinstance(dep, str) for dep in raw_build_deps):
    print('Error: build-system.requires must be a TOML list of strings.', file=sys.stderr)
    raise SystemExit(1)

if '*' in python_spec:
    print(f'Error: requires-python contains wildcard (*): {python_spec}', file=sys.stderr)
    raise SystemExit(1)
if re.search(r'(^|[^<>=!~])<[^=]', python_spec):
    print(f'Error: requires-python contains standalone < operator: {python_spec}', file=sys.stderr)
    raise SystemExit(1)
if re.search(r'(^|[^<>=!~])>[^=]', python_spec):
    print(f'Error: requires-python contains standalone > operator: {python_spec}', file=sys.stderr)
    raise SystemExit(1)
if not re.search(r'[<>=!~]=', python_spec):
    print(f'Error: requires-python must use version operators such as ==, >=, <=, ~=, or !=: {python_spec}', file=sys.stderr)
    raise SystemExit(1)

# -----------------------------------------------------------------------------
# Python version selection
# -----------------------------------------------------------------------------

def major_minor(version: str) -> str:
    match = re.match(r'(\d+)\.(\d+)', version)
    if not match:
        raise ValueError(f'not a Python major.minor version: {version}')
    return f'{match.group(1)}.{match.group(2)}'


def version_key(version: str) -> tuple[int, int]:
    major, minor = major_minor(version).split('.')
    return int(major), int(minor)


def extract_build_python(spec: str) -> str:
    parts = [part.strip() for part in spec.split(',') if part.strip()]
    exact_versions: list[str] = []
    lower_bound_versions: list[str] = []
    compatible_versions: list[str] = []

    for part in parts:
        match = re.match(
            r'(?P<op>===|==|~=|>=|<=|>|<|!=)?\s*'
            r'(?P<version>\d+\.\d+(?:\.\d+)?|\d+\.\d+\.\*)',
            part,
        )
        if not match:
            continue

        op = match.group('op') or ''
        version = match.group('version').replace('.*', '')

        if op in {'==', '==='}:
            exact_versions.append(major_minor(version))
        elif op == '~=':
            compatible_versions.append(major_minor(version))
        elif op == '>=':
            lower_bound_versions.append(major_minor(version))
        elif op == '>':
            print(
                f'Error: requires-python uses a strict > lower bound: {spec}. '
                'Use >=, ==, or ~= so this script can choose a build Python version.',
                file=sys.stderr,
            )
            raise SystemExit(1)

    if exact_versions:
        return sorted(set(exact_versions), key=version_key)[0]

    if compatible_versions:
        return sorted(set(compatible_versions), key=version_key)[0]

    if lower_bound_versions:
        return sorted(set(lower_bound_versions), key=version_key)[0]

    print(
        f'Error: could not extract a lower-bound build Python version from requires-python: {spec}',
        file=sys.stderr,
    )
    raise SystemExit(1)


build_python = extract_build_python(python_spec)

# -----------------------------------------------------------------------------
# Dependency mapping
# -----------------------------------------------------------------------------

import_name = import_name_override or name.replace('-', '_')
if not re.fullmatch(r'[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*', import_name):
    print(
        'Error: import name is not a valid Python import path. '
        'Set IMPORT_NAME_OVERRIDE to the importable module or package name.',
        file=sys.stderr,
    )
    raise SystemExit(1)


def normalize_conda_spec(dep: str) -> str:
    dep = dep.strip()
    return re.sub(r'\s*(===|==|~=|>=|<=|!=|>|<)\s*', r' \1', dep, count=1)


def conda_spec_name(dep: str) -> str:
    return re.split(r'\s*(?:===|==|~=|>=|<=|!=|>|<)\s*', dep, maxsplit=1)[0].strip().lower()


def map_dep_to_conda(dep: str) -> str:
    dep = dep.strip()
    dep = dep.split(';', 1)[0].strip()
    dep = re.sub(r'^([A-Za-z0-9_.-]+)\[[^]]+\]', r'\1', dep)
    if not dep:
        return ''

    dep = normalize_conda_spec(dep)
    dep_name = conda_spec_name(dep)
    if dep_name == 'torch':
        return 'pytorch' + dep[len(dep_name):]
    return dep


def append_unique_spec(items: list[str], dep: str) -> None:
    dep = map_dep_to_conda(dep)
    if not dep:
        return
    if conda_spec_name(dep) not in {conda_spec_name(item) for item in items}:
        items.append(dep)


host_deps: list[str] = []
append_unique_spec(host_deps, 'pip')
for dep in raw_build_deps:
    append_unique_spec(host_deps, dep)

run_deps: list[str] = []
for dep in raw_deps:
    append_unique_spec(run_deps, dep)

# -----------------------------------------------------------------------------
# meta.yaml writing
# -----------------------------------------------------------------------------

license_file = project_root / 'LICENSE'
license_file_line = '  license_file: LICENSE\n' if license_file.exists() else ''


def yaml_scalar(value: str) -> str:
    return json.dumps(value)


host_python = f'python {python_spec}'
run_python = f'python {python_spec}'

meta_lines = [
    'package:\n',
    f'  name: {yaml_scalar(name)}\n',
    f'  version: {yaml_scalar(version)}\n',
    '\n',
    'source:\n',
    f'  path: {yaml_scalar(str(project_root))}\n',
    '\n',
    'build:\n',
    '  noarch: python\n',
    '  number: 0\n',
    '  script: |\n',
    '    set -eux\n',
    '    unset PYTHONHOME PYTHONPATH || true\n',
    '    export PYTHONNOUSERSITE=1\n',
    '    _CONDA_SHIM_DIR="${TMPDIR:-/tmp}/conda-shim.$$"\n',
    '    mkdir -p "$_CONDA_SHIM_DIR"\n',
    '    cat > "$_CONDA_SHIM_DIR/conda" <<\'CONDA_SHIM\'\n',
    '    #!/usr/bin/env bash\n',
    '    unset PYTHONHOME PYTHONPATH\n',
    '    export PYTHONNOUSERSITE=1\n',
    f'    exec {shlex.quote(base_conda_exe)} "$@"\n',
    '    CONDA_SHIM\n',
    '    chmod +x "$_CONDA_SHIM_DIR/conda"\n',
    '    export PATH="$_CONDA_SHIM_DIR:$PATH"\n',
    '    hash -r\n',
    '    echo "PATH=$PATH"\n',
    '    echo "CONDA_PREFIX=${CONDA_PREFIX:-}"\n',
    '    echo "PREFIX=$PREFIX"\n',
    '    echo "BUILD_PREFIX=$BUILD_PREFIX"\n',
    '    which python\n',
    '    python -m pip --version\n',
    '    python -c "import sys; print(\'python executable:\', sys.executable); print(\'python version:\', sys.version); print(\'sys.path:\', sys.path)"\n',
    '    python -m pip install . --no-deps --no-build-isolation -vv\n',
    '\n',
    'requirements:\n',
    '  host:\n',
    f'    - {yaml_scalar(host_python)}\n',
]

for dep in host_deps:
    meta_lines.append(f'    - {yaml_scalar(dep)}\n')

meta_lines.extend([
    '  run:\n',
    f'    - {yaml_scalar(run_python)}\n',
])

for dep in run_deps:
    meta_lines.append(f'    - {yaml_scalar(dep)}\n')

test_code = (
    f'import {import_name} as _m; import importlib.metadata as m; '
    f"print('OK', m.version({name!r})); print('Import:', _m.__name__)"
)
test_command = 'python -c ' + shlex.quote(test_code)

meta_lines.extend([
    '\n',
    'test:\n',
    '  imports:\n',
    f'    - {import_name}\n',
    '  commands:\n',
    '    - ' + yaml_scalar(test_command) + '\n',
    '\n',
    'about:\n',
    f'  summary: {yaml_scalar(summary)}\n',
    f'  license: {yaml_scalar(license_id)}\n',
    license_file_line,
])

meta_yaml_path.write_text(''.join(meta_lines), encoding='utf-8')

# -----------------------------------------------------------------------------
# Shell metadata emitted for the Bash driver
# -----------------------------------------------------------------------------

values = {
    'CODE_NAME': name,
    'CODE_TAG': version,
    'SUMMARY': summary,
    'PYTHON_SPEC': python_spec,
    'PYTHON_VERSION': build_python,
    'IMPORT_NAME': import_name,
    'DEPENDENCIES': '|'.join(run_deps),
    'HOST_DEPENDENCIES': '|'.join(host_deps),
    'RECIPE_DIR': str(meta_yaml_path.parent),
}

for key, value in values.items():
    print(f'{key}={shlex.quote(value)}')
PY
}

load_generated_metadata() {
    # shellcheck disable=SC1090
    source "$METADATA_FILE"
}

# -----------------------------------------------------------------------------
# User-facing summary and confirmation
# -----------------------------------------------------------------------------

print_project_summary() {
    echo
    cat <<EOF2
If the package import name differs from the project name, set an explicit override before running the script.

Example:

  export IMPORT_NAME_OVERRIDE="my_package"
EOF2
    echo

    echo "Detected project settings:"
    echo "  package name:      $CODE_NAME"
    echo "  import name:       $IMPORT_NAME"
    echo "  version:           $CODE_TAG"
    echo "  summary:           $SUMMARY"
    echo "  requires-python:   $PYTHON_SPEC"
    echo "  build target py:   $PYTHON_VERSION"
    echo "  anaconda user:     $ANACONDA_USER_NAME"
    echo "  recipe directory:  $RECIPE_DIR"
    echo "  conda build root:  $BUILD_CROOT"
    echo "  base conda exe:    $BASE_CONDA_EXE"
    echo

    echo "Conda host build dependencies:"
    print_pipe_list "$HOST_DEPENDENCIES"
    echo

    echo "Conda run dependencies:"
    print_pipe_list "$DEPENDENCIES"
    echo
}

confirm_upload() {
    local reply

    read -r -p "Build and upload this package to anaconda.org? (Y/n) " reply
    echo

    if [[ "${reply:-Y}" != "Y" ]]; then
        echo "Aborted. Temporary files will now be removed."
        exit 0
    fi
}

# -----------------------------------------------------------------------------
# Conda build environment preparation
# -----------------------------------------------------------------------------

activate_base_conda() {
    eval "$(conda shell.bash hook)"

    while [[ "${CONDA_SHLVL:-0}" -gt 0 ]]; do
        conda deactivate || true
    done

    conda activate base
}

create_build_environment() {
    if command -v mamba >/dev/null 2>&1; then
        mamba create -y -n "$BUILD_ENV_NAME" -c conda-forge \
            "python=$PYTHON_VERSION" conda conda-build anaconda-client
    else
        conda create -y -n "$BUILD_ENV_NAME" -c conda-forge \
            "python=$PYTHON_VERSION" conda conda-build anaconda-client
    fi
}

locate_build_environment() {
    BUILD_ENV_DIR="$(conda env list | awk -v name="$BUILD_ENV_NAME" '$1 == name {print $NF; found=1} END {if (!found) exit 1}')"

    [[ -x "$BUILD_ENV_DIR/bin/conda-build" ]] || \
        die "conda-build executable not found in build environment: $BUILD_ENV_DIR"

    [[ -x "$BUILD_ENV_DIR/bin/anaconda" ]] || \
        die "anaconda-client executable not found in build environment: $BUILD_ENV_DIR"
}

check_build_environment() {
    run_isolated "$BUILD_ENV_DIR/bin/python" -c "import sys, conda, conda_build; print('python executable:', sys.executable); print('python version:', sys.version); print('conda version:', conda.__version__); print('conda module:', conda.__file__); print('conda-build module:', conda_build.__file__)"
    run_isolated "$BASE_CONDA_EXE" --version
}

# conda-build may execute a `conda` command from the same environment that
# provides the `conda-build` executable. In this use case that launcher has
# failed inside the recipe build with `ModuleNotFoundError: conda`. Keep the
# Python `conda` package in the helper environment for conda-build imports, but
# replace only the command-line launcher with a wrapper that delegates to base.
patch_build_environment_conda_launcher() {
    local build_env_conda_launcher
    local build_env_conda_real

    build_env_conda_launcher="$BUILD_ENV_DIR/bin/conda"
    build_env_conda_real="$BUILD_ENV_DIR/bin/conda.real"

    if [[ -x "$build_env_conda_launcher" && ! -e "$build_env_conda_real" ]]; then
        mv "$build_env_conda_launcher" "$build_env_conda_real"
        cat > "$build_env_conda_launcher" <<EOF_CONDA_WRAPPER
#!/usr/bin/env bash
unset PYTHONHOME PYTHONPATH
export PYTHONNOUSERSITE=1
export CONDA_EXE=${BASE_CONDA_EXE@Q}
export CONDA_PYTHON_EXE=${BASE_CONDA_PREFIX@Q}/bin/python
exec ${BASE_CONDA_EXE@Q} "\$@"
EOF_CONDA_WRAPPER
        chmod +x "$build_env_conda_launcher"
    fi

    run_isolated "$BUILD_ENV_DIR/bin/conda" --version
}

# -----------------------------------------------------------------------------
# Build and upload
# -----------------------------------------------------------------------------

display_recipe() {
    echo
    echo "Generated conda recipe:"
    echo "-----------------------"
    cat "$RECIPE_DIR/meta.yaml"
    echo "-----------------------"
}

build_artifact() {
    # Keep only the final output line in case conda-build emits warnings before
    # the artifact path.
    ARTIFACT="$(run_isolated "$BUILD_ENV_DIR/bin/conda-build" -c conda-forge --python "$PYTHON_VERSION" --croot "$BUILD_CROOT" "$RECIPE_DIR" --output | tail -n 1)"

    run_isolated "$BUILD_ENV_DIR/bin/conda-build" \
        -c conda-forge \
        --python "$PYTHON_VERSION" \
        --croot "$BUILD_CROOT" \
        "$RECIPE_DIR"

    [[ -f "$ARTIFACT" ]] || die "expected artifact not found: $ARTIFACT"

    echo
    echo "Selected artifact:"
    echo "  $ARTIFACT"
    echo
}

require_anaconda_token() {
    if [[ -z "${ANACONDA_API_TOKEN:-}" ]]; then
        echo "Error: ANACONDA_API_TOKEN is not set." >&2
        echo "Create an Anaconda.org API token and run:" >&2
        echo "  export ANACONDA_API_TOKEN='<token>'" >&2
        exit 1
    fi
}

upload_artifact() {
    echo "Using anaconda-client executable:"
    echo "  $BUILD_ENV_DIR/bin/anaconda"

    echo "Uploading to anaconda.org"
    run_isolated "$BUILD_ENV_DIR/bin/anaconda" \
        --token "$ANACONDA_API_TOKEN" \
        upload \
        --user "$ANACONDA_USER_NAME" \
        "$ARTIFACT"

    echo
    echo "Upload complete. Temporary build environment and conda-build intermediates will now be removed."
}

# -----------------------------------------------------------------------------
# Main control flow
# -----------------------------------------------------------------------------

main() {
    resolve_script_dir
    enter_project_root
    require_project_inputs
    find_base_conda
    find_metadata_python

    generate_recipe_and_metadata
    load_generated_metadata
    print_project_summary
    confirm_upload

    activate_base_conda
    create_build_environment
    locate_build_environment
    check_build_environment
    patch_build_environment_conda_launcher

    display_recipe
    build_artifact
    require_anaconda_token
    upload_artifact
}

main "$@"

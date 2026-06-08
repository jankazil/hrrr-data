#!/usr/bin/env bash

set -euo pipefail

# Build and upload a pure-Python conda package from the local working tree.
# The script may live in scripts/ and may be called from any working directory.

SCRIPT_SOURCE="${BASH_SOURCE[0]}"
while [[ -L "$SCRIPT_SOURCE" ]]; do
    SCRIPT_DIR="$(cd -P "$(dirname "$SCRIPT_SOURCE")" >/dev/null 2>&1 && pwd)"
    SCRIPT_SOURCE="$(readlink "$SCRIPT_SOURCE")"
    [[ "$SCRIPT_SOURCE" != /* ]] && SCRIPT_SOURCE="$SCRIPT_DIR/$SCRIPT_SOURCE"
done
SCRIPT_DIR="$(cd -P "$(dirname "$SCRIPT_SOURCE")" >/dev/null 2>&1 && pwd)"

if PROJECT_ROOT="$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel 2>/dev/null)"; then
    cd "$PROJECT_ROOT"
else
    echo "Error: could not locate the Git project root from $SCRIPT_DIR." >&2
    exit 1
fi

PROJECT_ROOT="$(pwd -P)"

ANACONDA_USER_NAME="${ANACONDA_USER_NAME:-jan.kazil}"
LICENSE_ID="${LICENSE_ID:-BSD-3-Clause}"
PYPROJECT="${PYPROJECT:-pyproject.toml}"
IMPORT_NAME_OVERRIDE="${IMPORT_NAME_OVERRIDE:-}"
BUILD_ENV_PREFIX="${BUILD_ENV_PREFIX:-conda-build-upload-tmp}"
BUILD_ENV_NAME="${BUILD_ENV_NAME:-${BUILD_ENV_PREFIX}-${BASHPID}}"
RECIPE_DIR="$(mktemp -d "${TMPDIR:-/tmp}/conda-recipe.XXXXXXXXXX")"
METADATA_FILE="$(mktemp "${TMPDIR:-/tmp}/conda-metadata.XXXXXXXXXX")"

cleanup() {
    local status=$?
    set +e

    if command -v conda >/dev/null 2>&1; then
        eval "$(conda shell.bash hook)" >/dev/null 2>&1 || true

        if conda env list | awk '{print $1}' | grep -Fxq "$BUILD_ENV_NAME"; then
            conda run -n "$BUILD_ENV_NAME" conda-build purge >/dev/null 2>&1 || true
        fi

        while [[ "${CONDA_SHLVL:-0}" -gt 0 ]]; do
            conda deactivate >/dev/null 2>&1 || break
        done

        conda env remove -n "$BUILD_ENV_NAME" -y >/dev/null 2>&1 || true
    fi

    rm -rf "$RECIPE_DIR"
    rm -f "$METADATA_FILE"
    exit "$status"
}
trap cleanup EXIT INT TERM

if [[ ! -f "$PYPROJECT" ]]; then
    echo "Error: could not find $PYPROJECT." >&2
    exit 1
fi

if ! command -v conda >/dev/null 2>&1; then
    echo "Error: conda is required on PATH." >&2
    exit 1
fi

if command -v python3 >/dev/null 2>&1; then
    PYTHON_FOR_METADATA="python3"
elif command -v python >/dev/null 2>&1; then
    PYTHON_FOR_METADATA="python"
else
    echo "Error: python or python3 is required on PATH to read $PYPROJECT." >&2
    exit 1
fi

"$PYTHON_FOR_METADATA" - "$PYPROJECT" "$IMPORT_NAME_OVERRIDE" "$LICENSE_ID" "$RECIPE_DIR/meta.yaml" "$PROJECT_ROOT" > "$METADATA_FILE" <<'PY'
from __future__ import annotations

import json
import re
import shlex
import sys
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:
    print("Error: Python 3.11+ is required, or install tomli and modify this script to import it.", file=sys.stderr)
    raise SystemExit(1)

pyproject_path = Path(sys.argv[1])
import_name_override = sys.argv[2]
license_id = sys.argv[3]
meta_yaml_path = Path(sys.argv[4])
project_root = Path(sys.argv[5]).resolve()

with pyproject_path.open("rb") as f:
    data = tomllib.load(f)

project = data.get("project", {})
name = project.get("name")
version = project.get("version")
summary = project.get("description")
python_spec = project.get("requires-python")
raw_deps = project.get("dependencies", []) or []

missing = [
    field
    for field, value in (
        ("project.name", name),
        ("project.version", version),
        ("project.description", summary),
        ("project.requires-python", python_spec),
    )
    if not value
]
if missing:
    print(f"Error: missing required metadata in {pyproject_path}: {', '.join(missing)}", file=sys.stderr)
    raise SystemExit(1)

if not isinstance(raw_deps, list) or not all(isinstance(dep, str) for dep in raw_deps):
    print("Error: project.dependencies must be a TOML list of strings.", file=sys.stderr)
    raise SystemExit(1)

if "*" in python_spec:
    print(f"Error: requires-python contains wildcard (*): {python_spec}", file=sys.stderr)
    raise SystemExit(1)
if re.search(r"(^|[^<>=!~])<[^=]", python_spec):
    print(f"Error: requires-python contains standalone < operator: {python_spec}", file=sys.stderr)
    raise SystemExit(1)
if re.search(r"(^|[^<>=!~])>[^=]", python_spec):
    print(f"Error: requires-python contains standalone > operator: {python_spec}", file=sys.stderr)
    raise SystemExit(1)
if not re.search(r"[<>=!~]=", python_spec):
    print(f"Error: requires-python must use version operators such as ==, >=, <=, ~=, or !=: {python_spec}", file=sys.stderr)
    raise SystemExit(1)

clean_spec = re.sub(r"(^|,)\s*!=\s*[^,]+", "", python_spec).strip(" ,")
version_match = re.search(r"\d+\.\d+(?:\.\d+)?", clean_spec)
if not version_match:
    print(f"Error: could not extract a build Python version from requires-python: {python_spec}", file=sys.stderr)
    raise SystemExit(1)
build_python = version_match.group(0)

import_name = import_name_override or name.replace("-", "_")
if not re.fullmatch(r"[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*", import_name):
    print(
        "Error: import name is not a valid Python import path. "
        "Set IMPORT_NAME_OVERRIDE to the importable module or package name.",
        file=sys.stderr,
    )
    raise SystemExit(1)


def map_dep_to_conda(dep: str) -> str:
    dep = dep.strip()
    dep = dep.split(";", 1)[0].strip()
    dep = re.sub(r"^([A-Za-z0-9_.-]+)\[[^]]+\]", r"\1", dep)
    if dep == "torch":
        return "pytorch"
    if dep.startswith("torch"):
        return "pytorch" + dep[len("torch"):]
    return dep

run_deps: list[str] = []
for dep in raw_deps:
    mapped = map_dep_to_conda(dep)
    if mapped and mapped not in run_deps:
        run_deps.append(mapped)

license_file = project_root / "LICENSE"
license_file_line = "  license_file: LICENSE\n" if license_file.exists() else ""

def yaml_scalar(value: str) -> str:
    return json.dumps(value)

host_python = f"python {python_spec}"
run_python = f"python {python_spec}"

meta_lines = [
    "package:\n",
    f"  name: {yaml_scalar(name)}\n",
    f"  version: {yaml_scalar(version)}\n",
    "\n",
    "source:\n",
    f"  path: {yaml_scalar(str(project_root))}\n",
    "\n",
    "build:\n",
    "  noarch: python\n",
    "  number: 0\n",
    "  script: python -m pip install . --no-build-isolation -vv\n",
    "\n",
    "requirements:\n",
    "  host:\n",
    f"    - {yaml_scalar(host_python)}\n",
    "    - pip\n",
    "    - setuptools >=77\n",
    "    - wheel\n",
    "  run:\n",
    f"    - {yaml_scalar(run_python)}\n",
]
for dep in run_deps:
    meta_lines.append(f"    - {yaml_scalar(dep)}\n")
meta_lines.extend([
    "\n",
    "test:\n",
    "  imports:\n",
    f"    - {import_name}\n",
    "  commands:\n",
    "    - " + yaml_scalar(
        f"python -c \"import {import_name} as _m; import importlib.metadata as m; "
        f"print('OK', m.version({name!r})); print('Import:', _m.__name__)\""
    ) + "\n",
    "\n",
    "about:\n",
    f"  summary: {yaml_scalar(summary)}\n",
    f"  license: {yaml_scalar(license_id)}\n",
    license_file_line,
])
meta_yaml_path.write_text("".join(meta_lines), encoding="utf-8")

values = {
    "CODE_NAME": name,
    "CODE_TAG": version,
    "SUMMARY": summary,
    "PYTHON_SPEC": python_spec,
    "PYTHON_VERSION": build_python,
    "IMPORT_NAME": import_name,
    "DEPENDENCIES": "|".join(run_deps),
    "RECIPE_DIR": str(meta_yaml_path.parent),
}
for key, value in values.items():
    print(f"{key}={shlex.quote(value)}")
PY

# shellcheck disable=SC1090
source "$METADATA_FILE"

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
echo

echo "Conda run dependencies:"
if [[ -n "$DEPENDENCIES" ]]; then
    OLD_IFS="$IFS"
    IFS='|'
    for dep in $DEPENDENCIES; do
        [[ -n "$dep" ]] && echo "  - $dep"
    done
    IFS="$OLD_IFS"
else
    echo "  (none)"
fi
echo

read -r -p "Build and upload this package to anaconda.org? (Y/n) " REPLY
echo
if [[ "${REPLY:-Y}" != "Y" ]]; then
    echo "Aborted. Temporary files will now be removed."
    exit 0
fi

eval "$(conda shell.bash hook)"
while [[ "${CONDA_SHLVL:-0}" -gt 0 ]]; do
    conda deactivate || true
done
conda activate base

if command -v mamba >/dev/null 2>&1; then
    mamba create -y -n "$BUILD_ENV_NAME" -c conda-forge conda-build anaconda-client
else
    conda create -y -n "$BUILD_ENV_NAME" -c conda-forge conda-build anaconda-client
fi

ARTIFACT="$(conda run -n "$BUILD_ENV_NAME" conda-build -c conda-forge --python "$PYTHON_VERSION" "$RECIPE_DIR" --output)"
conda run -n "$BUILD_ENV_NAME" conda-build -c conda-forge --python "$PYTHON_VERSION" "$RECIPE_DIR"

if [[ ! -f "$ARTIFACT" ]]; then
    echo "Error: expected artifact not found: $ARTIFACT" >&2
    exit 1
fi

echo "Selected artifact:"
echo "  $ARTIFACT"

echo "Using anaconda-client executable:"
conda run -n "$BUILD_ENV_NAME" which anaconda
conda run -n "$BUILD_ENV_NAME" anaconda --version

echo "Logging in to anaconda.org"
conda run -n "$BUILD_ENV_NAME" anaconda login

conda run -n "$BUILD_ENV_NAME" anaconda upload --user "$ANACONDA_USER_NAME" "$ARTIFACT"

echo
echo "Upload complete. Temporary build environment and conda-build intermediates will now be removed."

#!/usr/bin/env bash

set -euo pipefail

################################################################################
# Build and upload a pure-Python conda package from the local working tree
################################################################################

ANACONDA_USER_NAME='jan.kazil'
LICENSE_ID='BSD-3-Clause'
PYPROJECT="${PYPROJECT:-pyproject.toml}"
BUILD_ENV_NAME="${BUILD_ENV_NAME:-conda-build-tmp}"

trim() {
  printf '%s' "$1" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//'
}

map_dep_to_conda() {
  local dep
  dep="$(trim "$1")"

  if [[ "$dep" == torch ]]; then
    echo "pytorch"
  elif [[ "$dep" == torch* ]]; then
    echo "${dep/torch/pytorch}"
  else
    echo "$dep"
  fi
}

cleanup() {
  set +e
  if command -v conda >/dev/null 2>&1; then
    eval "$(conda shell.bash hook)"
    conda deactivate >/dev/null 2>&1 || true
    conda env remove -n "${BUILD_ENV_NAME}" -y >/dev/null 2>&1 || true
  fi
  rm -rf recipe
}
trap cleanup EXIT

if [[ ! -f "$PYPROJECT" ]]; then
  echo "Error: Could not find $PYPROJECT" >&2
  exit 1
fi

if ! command -v conda >/dev/null 2>&1 && ! command -v mamba >/dev/null 2>&1; then
  echo "Error: neither conda nor mamba is available on PATH." >&2
  exit 1
fi

################################################################################
# Extract metadata from pyproject.toml
################################################################################

PYTHON_SPEC=$(
  grep -E '^[[:space:]]*requires-python[[:space:]]*=' "$PYPROJECT" \
  | sed -E 's/.*requires-python[[:space:]]*=[[:space:]]*"([^"]+)".*/\1/'
)

if [[ -z "${PYTHON_SPEC:-}" ]]; then
  echo "Error: Could not find requires-python in $PYPROJECT" >&2
  exit 1
fi

if grep -q '\*' <<< "$PYTHON_SPEC"; then
  echo "Error: requires-python contains wildcard (*): $PYTHON_SPEC" >&2
  exit 1
fi

if grep -Eq '(^|[^<>=])<[^=]' <<< "$PYTHON_SPEC"; then
  echo "Error: requires-python contains standalone < operator: $PYTHON_SPEC" >&2
  exit 1
fi

if grep -Eq '(^|[^<>=])>[^=]' <<< "$PYTHON_SPEC"; then
  echo "Error: requires-python contains standalone > operator: $PYTHON_SPEC" >&2
  exit 1
fi

if ! grep -Eq '([><=]=)' <<< "$PYTHON_SPEC"; then
  echo "Error: requires-python must use at least one of ==, >=, <= : $PYTHON_SPEC" >&2
  exit 1
fi

CLEAN_SPEC=$(sed -E 's/(^|,)[[:space:]]*!=[^,"]+//g; s/^[[:space:],]+//; s/[[:space:],]+$//' <<< "$PYTHON_SPEC")
PYTHON_VERSION=$(grep -Eo '[0-9]+\.[0-9]+(\.[0-9]+)?' <<< "$CLEAN_SPEC" | head -n 1)

if [[ -z "${PYTHON_VERSION:-}" ]]; then
  echo "Error: Could not extract a valid Python version from requires-python: $PYTHON_SPEC" >&2
  exit 1
fi

CODE_NAME=""
CODE_TAG=""
SUMMARY=""
DEPS_LIST=""
in_proj=0
in_deps=0

while IFS= read -r line; do
  case "$line" in
    "[project]") in_proj=1; continue ;;
    "[["*"") ;;
    "["*"]")
      if [[ "$in_proj" -eq 1 && "$in_deps" -eq 0 ]]; then
        break
      fi
      ;;
  esac

  [[ "$in_proj" -eq 1 ]] || continue

  if [[ "$in_deps" -eq 1 ]]; then
    case "$line" in
      *"]"*) in_deps=0 ;;
    esac
    case "$line" in
      *\"*\"*)
        dep=${line#*\"}
        dep=${dep%\"*}
        dep=$(map_dep_to_conda "$dep")
        [[ -n "$dep" ]] && DEPS_LIST="${DEPS_LIST}|${dep}"
        ;;
    esac
    continue
  fi

  case "$line" in
    *"dependencies"*"[")
      in_deps=1
      case "$line" in
        *\"*\"*)
          dep=${line#*\"}
          dep=${dep%\"*}
          dep=$(map_dep_to_conda "$dep")
          [[ -n "$dep" ]] && DEPS_LIST="${DEPS_LIST}|${dep}"
          ;;
      esac
      continue
      ;;
  esac

  case "$line" in
    name[[:space:]]*=[[:space:]]*\"*\"*)
      val=${line#*=}
      val=${val#*\"}
      val=${val%\"*}
      CODE_NAME=$(trim "$val")
      ;;
  esac

  case "$line" in
    version[[:space:]]*=[[:space:]]*\"*\"*)
      val=${line#*=}
      val=${val#*\"}
      val=${val%\"*}
      CODE_TAG=$(trim "$val")
      ;;
  esac

  case "$line" in
    description[[:space:]]*=[[:space:]]*\"*\"*)
      val=${line#*=}
      val=${val#*\"}
      val=${val%\"*}
      SUMMARY=$(trim "$val")
      ;;
  esac
done < "$PYPROJECT"

if [[ -z "$CODE_NAME" || -z "$CODE_TAG" || -z "$SUMMARY" ]]; then
  echo "Error: failed to extract required project metadata from $PYPROJECT" >&2
  exit 1
fi

IMPORT_NAME=$(printf '%s' "$CODE_NAME" | tr '-' '_')
DEPENDENCIES="${DEPS_LIST#|}"

echo
echo "Detected project settings:"
echo "  package name:      $CODE_NAME"
echo "  import name:       $IMPORT_NAME"
echo "  version:           $CODE_TAG"
echo "  summary:           $SUMMARY"
echo "  requires-python:   $PYTHON_SPEC"
echo "  build target py:   $PYTHON_VERSION"
echo "  anaconda user:     $ANACONDA_USER_NAME"
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
  echo "Aborted."
  exit 0
fi

eval "$(conda shell.bash hook)"

while [[ "${CONDA_SHLVL:-0}" -gt 0 ]]; do
  conda deactivate || true
done

conda activate base

mkdir -p recipe

export CODE_NAME
export CODE_TAG
export SUMMARY
export IMPORT_NAME
export LICENSE_ID
export DEPENDENCIES

cat > recipe/meta.yaml <<'EOF'
{% set name = environ.get("CODE_NAME") %}
{% set version = environ.get("CODE_TAG") %}
{% set summary = environ.get("SUMMARY") %}
{% set license_id = environ.get("LICENSE_ID") %}
{% set import_name = environ.get("IMPORT_NAME") %}
{% set deps = (environ.get("DEPENDENCIES") or "").split("|") %}

package:
  name: {{ name }}
  version: {{ version }}

source:
  path: ..

build:
  noarch: python
  number: 0
  script: {{ PYTHON }} -m pip install . --no-build-isolation -vv

requirements:
  host:
    - python
    - pip
    - setuptools >=77
    - wheel
  run:
    - python
{% for dep in deps %}
{%   if dep %}
    - {{ dep }}
{%   endif %}
{% endfor %}

test:
  imports:
    - {{ import_name }}
  commands:
    - python -c "import {{ import_name }} as _m; import importlib.metadata as m; print('OK', m.version('{{ name }}')); print('Import:', _m.__name__)"

about:
  summary: {{ summary }}
  license: {{ license_id }}
  license_file: LICENSE
EOF

if command -v mamba >/dev/null 2>&1; then
  mamba create -y -n "${BUILD_ENV_NAME}" -c conda-forge conda-build anaconda-client
else
  conda create -y -n "${BUILD_ENV_NAME}" -c conda-forge conda-build anaconda-client
fi

conda activate "${BUILD_ENV_NAME}"

echo
echo "Using conda-build from:"
echo "  CONDA_PREFIX=$CONDA_PREFIX"
conda build --version
echo

conda build -c conda-forge --python "${PYTHON_VERSION}" recipe

CONDA_BLD_PATH="$(conda info --base)/conda-bld"

echo
echo "Built artifacts:"
find "$CONDA_BLD_PATH" -maxdepth 2 -type f \( -name "${CODE_NAME}-*.conda" -o -name "${CODE_NAME}-*.tar.bz2" \) -print || true
echo

ARTIFACT=$(
  find "$CONDA_BLD_PATH" -maxdepth 2 -type f -name "${CODE_NAME}-${CODE_TAG}-*.conda" | head -n 1
)

if [[ -z "${ARTIFACT:-}" ]]; then
  ARTIFACT=$(
    find "$CONDA_BLD_PATH" -maxdepth 2 -type f -name "${CODE_NAME}-${CODE_TAG}-*.tar.bz2" | head -n 1
  )
fi

if [[ -z "${ARTIFACT:-}" ]]; then
  echo "Error: no built artifact found for ${CODE_NAME} ${CODE_TAG}" >&2
  exit 1
fi

echo "Selected artifact:"
echo "  $ARTIFACT"
echo

echo "Logging in to anaconda.org"
anaconda login
echo

read -r -p "Upload artifact to anaconda.org user ${ANACONDA_USER_NAME}? (Y/n) " REPLY
echo
if [[ "${REPLY:-Y}" != "Y" ]]; then
  echo "Upload skipped."
  exit 0
fi

anaconda upload --user "${ANACONDA_USER_NAME}" "$ARTIFACT"

echo
echo "Upload complete."

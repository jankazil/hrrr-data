#!/bin/bash

set -eu

# Build, install, and test a **pure-Python** conda package from a Git tag.

# If your package is not pure-Python (requires compiled C/C++/Fortran or platform-specific libraries), remove `noarch: python` from the recipe and build per platform.

################################################################################
# User settings
################################################################################

ANACONDA_USER_NAME='jan.kazil'
export LICENSE_ID="BSD-3-Clause"

################################################################################
# Settings from pyproject.toml
################################################################################

#
# Extract metadata from pyproject.toml
#

PYPROJECT="${PYPROJECT:-pyproject.toml}"

# Python version from the line with requires-python and parse one version pattern (e.g. 3.10, 3.11.8)

PYTHON_VERSION=$(
  grep -E '^[[:space:]]*requires-python[[:space:]]*=' "$PYPROJECT" \
  | sed -E 's/.*requires-python[[:space:]]*=[[:space:]]*"([^"]+)".*/\1/' \
  | grep -Eo '[0-9]+\.[0-9]+(\.[0-9]+)?' \
  | head -n 1
)

if [[ -z "$PYTHON_VERSION" ]]; then
  echo "Error: Could not extract Python version from $PYPROJECT" >&2
  exit 1
fi

echo "Using Python ${PYTHON_VERSION} for build and upload"

CODE_NAME=""
CODE_TAG=""
SUMMARY=""
REPO_URL=""
DEPS_LIST=""
in_proj=0
in_deps=0

trim() {
  # trim leading/trailing spaces
  printf '%s' "$1" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//'
}

# Read file line by line
while IFS= read -r line; do
  # Detect section starts
  case "$line" in
    "[project]") in_proj=1; continue ;;
    "[["*"")     ;;  # ignore array-of-tables (not used here)
    "["*"]")
      # Another section begins
      if [ "$in_proj" -eq 1 ] && [ "$in_deps" -eq 0 ]; then
        break
      fi
      ;;
  esac

  [ "$in_proj" -eq 1 ] || continue

  # Dependencies block handling
  if [ "$in_deps" -eq 1 ]; then
    # End of the dependencies array?
    case "$line" in
      *"]"*) in_deps=0 ;;
    esac
    # Extract a quoted package if present: "pkgname",
    case "$line" in
      *\"*\"*)
        dep=${line#*\"}; dep=${dep%\"*}
        # Skip empty lines or comments
        [ -n "$dep" ] && DEPS_LIST="${DEPS_LIST}${dep} "
        ;;
    esac
    continue
  fi

  # Look for the start of dependencies array
  case "$line" in
    *"dependencies"*"[")
      in_deps=1
      # Also capture any package on the same line, if present (rare)
      case "$line" in
        *\"*\"*)
          dep=${line#*\"}; dep=${dep%\"*}
          [ -n "$dep" ] && DEPS_LIST="${DEPS_LIST}${dep} "
      esac
      continue
      ;;
  esac

  # name = "..."
  case "$line" in
    name[[:space:]]*=[[:space:]]*\"*\"*)
      val=${line#*=}
      val=${val#*\"}; val=${val%\"*}
      CODE_NAME=$(trim "$val")
      ;;
  esac

  # version = "..."
  case "$line" in
    version[[:space:]]*=[[:space:]]*\"*\"*)
      val=${line#*=}
      val=${val#*\"}; val=${val%\"*}
      CODE_TAG=$(trim "$val")
      ;;
  esac

  # description = "..."
  case "$line" in
    description[[:space:]]*=[[:space:]]*\"*\"*)
      val=${line#*=}
      val=${val#*\"}; val=${val%\"*}
      SUMMARY=$(trim "$val")
      ;;
  esac

done < "$PYPROJECT"

# Construct derived variables

IMPORT_NAME=$(printf '%s' "$CODE_NAME" | tr '-' '_')
REPO_URL="https://github.com/jankazil/${CODE_NAME}.git"
DEPENDENCIES=$(printf 'python %s' "$(trim "$DEPS_LIST")")

# Export variables

export CODE_NAME IMPORT_NAME CODE_TAG REPO_URL DEPENDENCIES SUMMARY

#
# Show settings for verification
#

echo
echo "Settings determined from pyproject.toml:"
echo
echo "CODE_NAME=$CODE_NAME"
echo "IMPORT_NAME=$IMPORT_NAME"
echo "CODE_TAG=$CODE_TAG"
echo "SUMMARY=$SUMMARY"
echo "REPO_URL=$REPO_URL"
echo "DEPENDENCIES=$DEPENDENCIES"

echo ""
read -p "This script will attempt to create a conda package and upload it to anaconda.org. Continue (y/n)? "
echo ""

if [[  $REPLY != "y" ]] ; then
  echo "Nothing done."
  exit
fi

################################################################################
# Automatic part
################################################################################

#
# 0) Conda environment
#

# Deactivate all environments

for i in $(seq ${CONDA_SHLVL}); do
  eval "$(conda shell.bash hook)" # (this is necessary if we are running in a script)
  conda deactivate
done

# Activate base environment

eval "$(conda shell.bash hook)" # (this is necessary if we are running in a script)
conda activate base

#
# 1) Create required local files and folders
#

mkdir -p recipe

#
# 2) Generate a valid `recipe/meta.yaml` from your variables
#

# This recipe:
# - Builds **noarch** (pure-Python) via `pip install .` into the correct prefix using `$PYTHON`.
# - Pulls source from your **Git tag** for reproducibility.
# - Expands `DEPENDENCIES` into the `run` section automatically using Jinja and environment variables.
# - Includes `setuptools` and `wheel` in the **host** section to satisfy modern `pyproject.toml` builds (prevents `BackendUnavailable: Cannot import 'setuptools.build_meta'`).
# - Uses **single-line** test commands (no YAML here-docs) to avoid parser errors.
# - Imports your module and prints its package version.

cat > recipe/meta.yaml <<'EOF'
{% set name = environ.get("CODE_NAME") %}
{% set version = environ.get("CODE_TAG") %}
{% set repo = environ.get("REPO_URL") %}
{% set summary = environ.get("SUMMARY") %}
{% set license_id = environ.get("LICENSE_ID") %}
{% set import_name = environ.get("IMPORT_NAME") %}
{% set deps = (environ.get("DEPENDENCIES") or "").split() %}

package:
  name: {{ name }}
  version: {{ version }}

source:
  git_url: {{ repo }}
  git_rev: {{ version }}

build:
  noarch: python
  number: 0
  script: $PYTHON -m pip install . -vv

requirements:
  host:
    - python
    - pip
    - setuptools
    - wheel
  run:
{% for dep in deps %}
    - {{ dep }}
{% endfor %}

test:
  commands:
    - python -c "import {{ import_name }} as _m; import importlib.metadata as m; print('OK', m.version('{{ name }}')); print('Import:', _m.__name__)"
  imports:
    - {{ import_name }}

about:
  home: {{ repo }}
  summary: {{ summary }}
  license: {{ license_id }}
  license_file: LICENSE
EOF

#
# 3) Prepare a dedicated build environment
#

mamba create -y -n conda-build -c conda-forge python=${PYTHON_VERSION} conda-build anaconda-client
conda activate conda-build
conda build --version

#
# 4) Build the package
#

conda build -c conda-forge --python "${PYTHON_VERSION}" recipe

# Optional - List the produced artifacts

BLD_DIR="$CONDA_PREFIX/conda-bld"
find "$BLD_DIR" -maxdepth 2 -type f \( -name "${CODE_NAME}-*.conda" -o -name "${CODE_NAME}-*.tar.bz2" \) -print

#
# 5) Upload to personal Anaconda.org account
#

# Log in once (will store token in ~/.conda/anaconda.yaml)

echo
echo "Loggin in to anaconda.org:"
echo
anaconda login

# Upload your built package from your local conda-bld directory

# Point to the actual build folder
export BLD_DIR="$CONDA_PREFIX/conda-bld"

# Verify the artifact location and name
find "$BLD_DIR" -maxdepth 2 -type f \( -name "${CODE_NAME}-*.conda" -o -name "${CODE_NAME}-*.tar.bz2" \) -print

# Upload the noarch build to your user channel

echo ""
read -p "Upload to anaconda.org (y/n)? "
echo ""

if [[  $REPLY != "y" ]] ; then
  echo "Nothing done."
  exit
fi

anaconda upload "$BLD_DIR/noarch/${CODE_NAME}-${CODE_TAG}-"*.conda --user ${ANACONDA_USER_NAME} || true

#
# 6) Cleanup
#

# Deactivate and remove build environment

conda deactivate
conda env remove -n conda-build -y

# Remove temporary directories

rm -rf recipe

#
# 7) Optional - Test by creating an environment for the package and then installing it from personal channel
#

#mamba create -n "${CODE_NAME}" -c ${ANACONDA_USER_NAME} -c conda-forge "${CODE_NAME}"

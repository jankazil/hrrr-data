#!/usr/bin/env bash

set -euo pipefail

# setup-dev-env.sh creates a fresh local development environment for the project.
# It removes any existing conda environment with the project’s environment name,
# recreates it from environment.yml, installs the package in editable development
# mode, replaces any existing Jupyter kernelspec with the project’s repository
# name, registers the new kernel, and installs the project’s pre-commit hooks.
# It is intended to be run from the generated project via:
#
# make setup-dev-env

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." >/dev/null 2>&1 && pwd)"
cd "$PROJECT_ROOT"

ENV_NAME="hrrr_data"
KERNEL_NAME="hrrr-data"
ENV_FILE="environment.yml"

if ! command -v conda >/dev/null 2>&1; then
  echo "Error: conda was not found." >&2
  exit 1
fi

if command -v mamba >/dev/null 2>&1; then
  ENV_CREATE_FRONTEND="mamba"
else
  ENV_CREATE_FRONTEND="conda"
fi

if conda env list | awk '{print $1}' | grep -Fxq "$ENV_NAME"; then
  echo "Removing existing conda environment: $ENV_NAME"
  conda env remove -y -n "$ENV_NAME"
fi

echo "Creating conda environment: $ENV_NAME"
"$ENV_CREATE_FRONTEND" env create -f "$ENV_FILE"

if conda run -n "$ENV_NAME" python -m jupyter kernelspec list 2>/dev/null | awk '{print $1}' | grep -Fxq "$KERNEL_NAME"; then
  echo "Removing existing Jupyter kernel: $KERNEL_NAME"
  conda run -n "$ENV_NAME" python -m jupyter kernelspec remove -f "$KERNEL_NAME"
fi

echo "Installing project in editable development mode."
conda run -n "$ENV_NAME" python -m pip install --no-deps -e '.[dev]'

echo "Installing Jupyter kernel: $KERNEL_NAME"
conda run -n "$ENV_NAME" python -m ipykernel install --user \
  --name "$KERNEL_NAME" \
  --display-name "$KERNEL_NAME"

echo "Installing pre-commit hooks."
conda run -n "$ENV_NAME" pre-commit install

echo
echo "Development environment ready."
echo
echo "Activate with:"
echo "  conda activate $ENV_NAME"

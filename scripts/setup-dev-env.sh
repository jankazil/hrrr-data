#!/usr/bin/env bash

set -euo pipefail

# setup-dev-env.sh creates a fresh local development environment for the project.
# It removes any existing conda environment with the project’s development
# environment name, recreates it from environment.yml, installs the package in
# editable development mode, replaces any existing Jupyter kernelspec with the
# project’s repository name, registers the new kernel, and installs the project’s
# pre-commit hooks. It is intended to be run from the generated project via:
#
# make setup-dev-env

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." >/dev/null 2>&1 && pwd)"
cd "$PROJECT_ROOT"

ENV_FILE="environment.yml"

#
# Create environment-dev.yml from environment.yml
#

ENV_DEV_FILE='environment-dev.yml'

# Extract the first environment name.
ENV_NAME="$(
    sed -nE \
        's/^[[:space:]]*name:[[:space:]]*([^[:space:]#]+).*/\1/p' \
        "$ENV_FILE" |
    head -n 1
)"

if [[ -z "$ENV_NAME" ]]; then
    printf 'Error: no environment name found in %s\n' "$ENV_FILE" >&2
    exit 1
fi

ENV_DEV_NAME="${ENV_NAME}-dev"
KERNEL_DEV_NAME=${ENV_DEV_NAME}

# Copy the file while replacing only the first name field.
awk -v new_name="$ENV_DEV_NAME" '
    !replaced && /^[[:space:]]*name:[[:space:]]*/ {
        sub(/name:[[:space:]]*.*/, "name: " new_name)
        replaced = 1
    }
    { print }
' "$ENV_FILE" > "$ENV_DEV_FILE"

printf 'Created %s with environment name %s\n' \
    "$ENV_DEV_FILE" "$ENV_DEV_NAME"

#
# Check for conda/mamba
#

if ! command -v conda >/dev/null 2>&1; then
  echo "Error: conda was not found." >&2
  exit 1
fi

if command -v mamba >/dev/null 2>&1; then
  ENV_CREATE_FRONTEND="mamba"
else
  ENV_CREATE_FRONTEND="conda"
fi

#
# Remove any existing environment
#

if conda env list | awk '{print $1}' | grep -Fxq "$ENV_DEV_NAME"; then
  echo "Removing existing conda environment: $ENV_DEV_NAME"
  conda env remove -y -n "$ENV_DEV_NAME"
fi

#
# Create environment
#

echo "Creating conda environment: $ENV_DEV_NAME"
"$ENV_CREATE_FRONTEND" env create -f "$ENV_DEV_FILE"

#
# Remove any existing Jupyter kernel
#

if conda run -n "$ENV_DEV_NAME" python -m jupyter kernelspec list 2>/dev/null | awk '{print $1}' | grep -Fxq "$KERNEL_DEV_NAME"; then
  echo "Removing existing Jupyter kernel: $KERNEL_DEV_NAME"
  conda run -n "$ENV_DEV_NAME" python -m jupyter kernelspec remove -f "$KERNEL_DEV_NAME"
fi

#
# Install project
#

echo "Installing project in editable development mode."
conda run -n "$ENV_DEV_NAME" python -m pip install --no-deps -e '.[dev]'

#
# Install Jupyter kernel
#

echo "Installing Jupyter kernel: $KERNEL_DEV_NAME"
conda run -n "$ENV_DEV_NAME" python -m ipykernel install --user \
  --name "$KERNEL_DEV_NAME" \
  --display-name "$KERNEL_DEV_NAME"

#
# Pre-commit hooks
#

echo "Installing pre-commit hooks."
conda run -n "$ENV_DEV_NAME" pre-commit install

echo
echo "Development environment ready."
echo
echo "Activate with:"
echo "  conda activate $ENV_DEV_NAME"

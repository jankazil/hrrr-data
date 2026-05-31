#!/usr/bin/env bash

set -o errexit
set -o nounset
set -o pipefail

# Locate and enter the Git project root, so this script can live in scripts/
# and still be called from any working directory.
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

# Check that Python is available
if ! command -v python >/dev/null 2>&1; then
    echo "Error: python is not installed or not in PATH."
    exit 1
fi

install_missing_deps() {
    local missing=("$@")

    echo "Missing required Python packages: ${missing[*]}"
    echo "Choose how to install them:"
    echo "  1) pip"
    echo "  2) conda"
    echo "  3) mamba"
    read -r -p "Enter choice [1-3]: " install_choice

    case "${install_choice}" in
        1)
            python -m pip install "${missing[@]}"
            ;;
        2)
            if ! command -v conda >/dev/null 2>&1; then
                echo "Error: conda is not installed or not in PATH."
                exit 1
            fi
            conda install -y "${missing[@]}"
            ;;
        3)
            if ! command -v mamba >/dev/null 2>&1; then
                echo "Error: mamba is not installed or not in PATH."
                exit 1
            fi
            mamba install -y "${missing[@]}"
            ;;
        *)
            echo "Error: invalid selection."
            exit 1
            ;;
    esac
}

missing_packages=()

if ! python -c "import build" >/dev/null 2>&1; then
    missing_packages+=("build")
fi

if ! python -c "import twine" >/dev/null 2>&1; then
    missing_packages+=("twine")
fi

if [[ ${#missing_packages[@]} -gt 0 ]]; then
    install_missing_deps "${missing_packages[@]}"
fi

# Re-check after attempted install
if ! python -c "import build" >/dev/null 2>&1; then
    echo "Error: Python package 'build' is still not available."
    exit 1
fi

if ! python -c "import twine" >/dev/null 2>&1; then
    echo "Error: Python package 'twine' is still not available."
    exit 1
fi

# Ask for PyPI token
read -r -s -p "Enter your TWINE_PASSWORD (PyPI token): " TWINE_PASSWORD
echo
if [[ -z "${TWINE_PASSWORD}" ]]; then
    echo "Error: TWINE_PASSWORD was not provided."
    exit 1
fi

export TWINE_USERNAME="__token__"
export TWINE_PASSWORD

# Remove earlier builds
echo "Removing earlier builds..."
rm -rf dist/ build/ ./*.egg-info

# Build package
echo "Building package..."
if ! python -m build; then
    echo "Error: Build failed."
    exit 1
fi

# Verify build artifacts exist
if [[ ! -d dist ]] || [[ -z "$(find dist -maxdepth 1 -type f 2>/dev/null)" ]]; then
    echo "Error: No build artifacts were created in dist/."
    exit 1
fi

# Check distributions with twine
echo "Checking distributions..."
if ! python -m twine check dist/*; then
    echo "Error: twine check failed."
    exit 1
fi

echo "Build and validation completed successfully."

# Ask whether to upload
read -r -p "Upload to PyPI now? [y/N]: " upload_choice
case "${upload_choice}" in
    [yY]|[yY][eE][sS])
        echo "Uploading to PyPI..."
        python -m twine upload dist/*
        ;;
    *)
        echo "Upload skipped."
        ;;
esac

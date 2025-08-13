from importlib.metadata import PackageNotFoundError, version

# Distribution name as published (matches [project].name in pyproject.toml)
_DIST_NAME = "arotake"

try:
    __version__ = version(_DIST_NAME)
except PackageNotFoundError:
    # Fallback to import package name; if still not installed, use local tag
    pkg = __package__ or __name__.split(".", 1)[0]
    try:
        __version__ = version(pkg)
    except PackageNotFoundError:
        __version__ = "0.0.0+local"

__all__ = ["__version__"]

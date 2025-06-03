# Automatically generate the version number from pyproject.toml

def _get_version_from_toml():
    import tomllib
    from pathlib import Path

    toml_file = Path(__file__).parent.parent / 'pyproject.toml'
    with open(toml_file, 'rb') as f:
        pyproject = tomllib.load(f)
    return pyproject['project']['version']

__version__ = _get_version_from_toml()
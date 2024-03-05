def _get_version() -> str:
    from pathlib import Path

    import versioningit

    import broadbean

    project_dir = Path(broadbean.__file__).parent.parent.parent
    return versioningit.get_version(project_dir=project_dir)


__version__ = _get_version()

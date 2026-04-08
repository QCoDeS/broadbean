"""Waveform Designer - Django-based waveform design application.

This package provides a web-based interface for designing and managing
waveform sequences for arbitrary waveform generators (AWGs).

Usage:
    # From command line
    broadbean-designer runserver

    # Or programmatically
    from broadbean.designer import main
    main()
"""

import os
import sys


def main():
    """CLI entry point for broadbean-designer command.

    This function sets up Django and executes management commands.
    Typical usage: broadbean-designer runserver [port]
    """
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "broadbean.designer.settings")

    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed? "
            "Install with: pip install broadbean[designer]"
        ) from exc

    # If no arguments provided, default to runserver
    if len(sys.argv) == 1:
        sys.argv.append("runserver")

    execute_from_command_line(sys.argv)


def run(host: str = "127.0.0.1", port: int = 8000):
    """Programmatic entry point to run the designer server.

    Args:
        host: Host address to bind to (default: 127.0.0.1)
        port: Port number to listen on (default: 8000)
    """
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "broadbean.designer.settings")

    from django.core.management import execute_from_command_line

    # Run migrations first
    execute_from_command_line(["manage.py", "migrate", "--run-syncdb"])

    # Start the server
    execute_from_command_line(["manage.py", "runserver", f"{host}:{port}"])

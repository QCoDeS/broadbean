#!/usr/bin/env python
"""Django management script for broadbean designer.

This module provides compatibility for running management commands via:
    python -m broadbean.designer.manage <command>

The main entry point is in broadbean.designer.__init__.py
"""
from broadbean.designer import main

if __name__ == "__main__":
    main()

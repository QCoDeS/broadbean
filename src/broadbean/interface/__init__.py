"""Factory interfaces for instrument creation.

This package provides factory classes for creating AWG and Scope
instances based on configuration.
"""

from broadbean.interface.awg import AWGFactory, create_mock_awg
from broadbean.interface.scope import ScopeFactory, create_mock_scope

__all__ = [
    "AWGFactory",
    "ScopeFactory",
    "create_mock_awg",
    "create_mock_scope",
]

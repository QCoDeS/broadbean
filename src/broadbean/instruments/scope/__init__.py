"""Scope instrument implementations.

This package contains implementations of Scope
for various hardware vendors.
"""

# Import implementations to trigger registration with InstrumentRegistry
from broadbean.instruments.scope.tektronix import (
    TektronixDPO70000,
    TektronixDPO7200,
)

__all__ = [
    "TektronixDPO70000",
    "TektronixDPO7200",
]

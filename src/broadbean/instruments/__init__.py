"""Instrument control infrastructure for broadbean.

This package provides:
- Abstract base classes for AWG and Scope instruments
- Registry pattern for instrument driver registration
- Mock implementations for simulation/testing
- Hardware driver implementations (Tektronix)
"""

from broadbean.instruments.registry import (
    AWGDriver,
    InstrumentRegistry,
    ScopeDriver,
)

__all__ = [
    "AWGDriver",
    "ScopeDriver",
    "InstrumentRegistry",
]

"""Instrument control infrastructure for broadbean.

This package provides:
- Abstract base classes for AWG and Scope instruments
- Registry pattern for instrument driver registration
- Mock implementations for simulation/testing
- Hardware driver implementations (Tektronix)
"""

from broadbean.instruments.registry import (
    AWGDriver,
    ScopeDriver,
    InstrumentRegistry,
)

__all__ = [
    "AWGDriver",
    "ScopeDriver",
    "InstrumentRegistry",
]

"""AWG instrument implementations.

This package contains implementations of ArbitraryWaveformGenerator
for various hardware vendors.
"""

# Import implementations to trigger registration with InstrumentRegistry
from broadbean.instruments.awg.tektronix import (
    TektronixAWG70001A,
    TektronixAWG70002A,
)

__all__ = [
    "TektronixAWG70001A",
    "TektronixAWG70002A",
]

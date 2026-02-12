"""AWG Factory for creating AWG instances based on configuration.

This module provides the AWGFactory class that creates appropriate AWG
implementations based on configuration using the InstrumentRegistry.
"""

import logging

from broadbean.instruments.base.awg import ArbitraryWaveformGenerator
from broadbean.instruments.registry import InstrumentRegistry

# Import implementations to trigger registration with InstrumentRegistry
import broadbean.instruments.mock  # noqa: F401

# Try to import hardware drivers (optional dependency)
try:
    import broadbean.instruments.awg  # noqa: F401
except ImportError:
    pass  # Hardware drivers not available

logger = logging.getLogger(__name__)


class AWGFactory:
    """Factory class for creating AWG instances.

    This factory supports two main use cases:
    1. From a database configuration model (AWGStationConfig)
    2. From a configuration dictionary

    The factory uses InstrumentRegistry to create the appropriate
    implementation based on the driver_type.
    """

    @classmethod
    def create_from_model(cls, config_model) -> ArbitraryWaveformGenerator:
        """Create AWG instance from a Django model instance.

        Args:
            config_model: AWGStationConfig model instance with properties:
                - driver_type: Driver key (e.g., "mock", "tektronix_awg70002a")
                - use_flags: bool for sequence output flags
                - to_config_dict(): method returning configuration dict

        Returns:
            ArbitraryWaveformGenerator: AWG instance
        """
        driver_key = config_model.driver_type
        config = config_model.to_config_dict()
        flags = getattr(config_model, "use_flags", False)

        logger.info(
            "Creating AWG from model: driver=%s, flags=%s",
            driver_key,
            flags,
        )
        return InstrumentRegistry.create_awg(driver_key, config, flags=flags)

    @classmethod
    def create_from_config_dict(
        cls,
        config_dict: dict,
        flags: bool = False,
    ) -> ArbitraryWaveformGenerator:
        """Create AWG instance from a configuration dictionary.

        Args:
            config_dict: Configuration dictionary with:
                - driver_type: Driver key (e.g., "mock", "tektronix_awg70002a")
                - address: VISA address for real instruments
                - parameters: Optional instrument parameters
            flags: Whether to use flags in sequence output

        Returns:
            ArbitraryWaveformGenerator: AWG instance
        """
        driver_key = config_dict.get("driver_type", "mock")

        logger.info(
            "Creating AWG from config dict: driver=%s, flags=%s",
            driver_key,
            flags,
        )
        return InstrumentRegistry.create_awg(driver_key, config_dict, flags=flags)


def create_mock_awg() -> ArbitraryWaveformGenerator:
    """Convenience function to create a mock AWG instance.

    Returns:
        ArbitraryWaveformGenerator: Mock AWG instance for simulation
    """
    return InstrumentRegistry.create_awg("mock", {})

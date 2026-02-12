"""Scope Factory for creating Scope instances based on configuration.

This module provides the ScopeFactory class that creates appropriate Scope
implementations based on configuration using the InstrumentRegistry.
"""

import logging

from broadbean.instruments.base.scope import Scope
from broadbean.instruments.registry import InstrumentRegistry

# Import implementations to trigger registration with InstrumentRegistry
import broadbean.instruments.mock  # noqa: F401

# Try to import hardware drivers (optional dependency)
try:
    import broadbean.instruments.scope  # noqa: F401
except ImportError:
    pass  # Hardware drivers not available

logger = logging.getLogger(__name__)


class ScopeFactory:
    """Factory class for creating Scope instances.

    This factory supports two main use cases:
    1. From a database configuration model (ScopeStationConfig)
    2. From a configuration dictionary

    The factory uses InstrumentRegistry to create the appropriate
    implementation based on the driver_type.
    """

    @classmethod
    def create_from_model(cls, config_model) -> Scope:
        """Create Scope instance from a Django model instance.

        Args:
            config_model: ScopeStationConfig model instance with properties:
                - driver_type: Driver key (e.g., "mock", "tektronix_dpo70000")
                - to_config_dict(): method returning configuration dict

        Returns:
            Scope: Scope instance
        """
        driver_key = config_model.driver_type
        config = config_model.to_config_dict()

        logger.info("Creating Scope from model: driver=%s", driver_key)
        return InstrumentRegistry.create_scope(driver_key, config)

    @classmethod
    def create_from_config_dict(cls, config_dict: dict) -> Scope:
        """Create Scope instance from a configuration dictionary.

        Args:
            config_dict: Configuration dictionary with:
                - driver_type: Driver key (e.g., "mock", "tektronix_dpo70000")
                - address: VISA address for real instruments
                - parameters: Optional instrument parameters

        Returns:
            Scope: Scope instance
        """
        driver_key = config_dict.get("driver_type", "mock")

        logger.info("Creating Scope from config dict: driver=%s", driver_key)
        return InstrumentRegistry.create_scope(driver_key, config_dict)


def create_mock_scope() -> Scope:
    """Convenience function to create a mock Scope instance.

    Returns:
        Scope: Mock Scope instance for simulation
    """
    return InstrumentRegistry.create_scope("mock", {})

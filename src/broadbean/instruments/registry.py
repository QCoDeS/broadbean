"""Central registry for instrument implementations.

This module provides a registration system for AWG and Scope implementations,
allowing new instrument types to be added without modifying factory code.

Usage:
    @InstrumentRegistry.register_awg("my_awg_driver")
    class MyAWG(ArbitraryWaveformGenerator):
        ...
"""

import logging
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class AWGDriver(Enum):
    """Supported AWG driver types.

    Add new AWG drivers here when implementing support for new instruments.
    """

    MOCK = "mock"
    TEKTRONIX_70002A = "tektronix_awg70002a"
    TEKTRONIX_70001A = "tektronix_awg70001a"
    # Future examples:
    # KEYSIGHT_M8195A = "keysight_m8195a"
    # TABOR_P9484M = "tabor_p9484m"


class ScopeDriver(Enum):
    """Supported Scope driver types.

    Add new Scope drivers here when implementing support for new instruments.
    """

    MOCK = "mock"
    TEKTRONIX_DPO70000 = "tektronix_dpo70000"
    TEKTRONIX_DPO7200 = "tektronix_dpo7200"
    # Future examples:
    # LECROY_WR8000 = "lecroy_wr8000"
    # KEYSIGHT_INFINIIUM = "keysight_infiniium"


class InstrumentRegistry:
    """Registry for AWG and Scope implementations.

    This class provides a central registry for instrument implementations,
    using decorators for registration and factory methods for instantiation.

    Example:
        # Register an implementation
        @InstrumentRegistry.register_awg("my_driver")
        class MyAWG(ArbitraryWaveformGenerator):
            def __init__(self, config: dict, **kwargs):
                ...

        # Create an instance
        awg = InstrumentRegistry.create_awg("my_driver", config_dict)
    """

    _awg_registry: dict[str, type] = {}
    _scope_registry: dict[str, type] = {}

    @classmethod
    def register_awg(cls, driver_key: str):
        """Decorator to register an AWG implementation.

        Args:
            driver_key: Unique identifier for the AWG driver (should match
                       an AWGDriver enum value).

        Returns:
            Decorator function that registers the class.

        Example:
            @InstrumentRegistry.register_awg("tektronix_awg70002a")
            class TektronixAWG70002A(ArbitraryWaveformGenerator):
                ...
        """

        def decorator(impl_class: type) -> type:
            if driver_key in cls._awg_registry:
                logger.warning(
                    "AWG driver '%s' already registered, overwriting with %s",
                    driver_key,
                    impl_class.__name__,
                )
            cls._awg_registry[driver_key] = impl_class
            logger.debug(
                "Registered AWG driver: %s -> %s", driver_key, impl_class.__name__
            )
            return impl_class

        return decorator

    @classmethod
    def register_scope(cls, driver_key: str):
        """Decorator to register a Scope implementation.

        Args:
            driver_key: Unique identifier for the Scope driver (should match
                       a ScopeDriver enum value).

        Returns:
            Decorator function that registers the class.

        Example:
            @InstrumentRegistry.register_scope("tektronix_dpo70000")
            class TektronixDPO70000(Scope):
                ...
        """

        def decorator(impl_class: type) -> type:
            if driver_key in cls._scope_registry:
                logger.warning(
                    "Scope driver '%s' already registered, overwriting with %s",
                    driver_key,
                    impl_class.__name__,
                )
            cls._scope_registry[driver_key] = impl_class
            logger.debug(
                "Registered Scope driver: %s -> %s", driver_key, impl_class.__name__
            )
            return impl_class

        return decorator

    @classmethod
    def create_awg(cls, driver_key: str, config: dict, **kwargs) -> Any:
        """Create an AWG instance from the registry.

        Args:
            driver_key: The registered driver key (e.g., "tektronix_awg70002a").
            config: Configuration dictionary with address, parameters, etc.
            **kwargs: Additional arguments passed to the implementation constructor
                     (e.g., flags=True for Tektronix AWGs).

        Returns:
            An instance of ArbitraryWaveformGenerator.

        Raises:
            ValueError: If the driver_key is not registered.
        """
        impl_class = cls._awg_registry.get(driver_key)
        if impl_class is None:
            available = list(cls._awg_registry.keys())
            raise ValueError(
                f"Unknown AWG driver: '{driver_key}'. Available drivers: {available}"
            )
        logger.info("Creating AWG instance: %s (%s)", driver_key, impl_class.__name__)
        return impl_class(config=config, **kwargs)

    @classmethod
    def create_scope(cls, driver_key: str, config: dict, **kwargs) -> Any:
        """Create a Scope instance from the registry.

        Args:
            driver_key: The registered driver key (e.g., "tektronix_dpo70000").
            config: Configuration dictionary with address, parameters, etc.
            **kwargs: Additional arguments passed to the implementation constructor.

        Returns:
            An instance of Scope.

        Raises:
            ValueError: If the driver_key is not registered.
        """
        impl_class = cls._scope_registry.get(driver_key)
        if impl_class is None:
            available = list(cls._scope_registry.keys())
            raise ValueError(
                f"Unknown Scope driver: '{driver_key}'. Available drivers: {available}"
            )
        logger.info("Creating Scope instance: %s (%s)", driver_key, impl_class.__name__)
        return impl_class(config=config, **kwargs)

    @classmethod
    def get_awg_choices(cls) -> list[tuple[str, str]]:
        """Get list of AWG driver choices for UI dropdowns.

        Returns:
            List of (value, label) tuples suitable for Django choice fields.
        """
        choices = []
        for driver in AWGDriver:
            if driver == AWGDriver.MOCK:
                label = "Mock/Simulation"
            else:
                # Derive label from enum value
                # e.g., "tektronix_awg70002a" -> "Tektronix AWG70002A"
                parts = driver.value.split("_")
                label = " ".join(p.capitalize() if p.islower() else p for p in parts)
            choices.append((driver.value, label))
        return choices

    @classmethod
    def get_scope_choices(cls) -> list[tuple[str, str]]:
        """Get list of Scope driver choices for UI dropdowns.

        Returns:
            List of (value, label) tuples suitable for Django choice fields.
        """
        choices = []
        for driver in ScopeDriver:
            if driver == ScopeDriver.MOCK:
                label = "Mock/Simulation"
            else:
                # Derive label from enum value
                # e.g., "tektronix_dpo70000" -> "Tektronix DPO70000"
                parts = driver.value.split("_")
                label = " ".join(
                    p.capitalize() if p.islower() else p.upper() for p in parts
                )
            choices.append((driver.value, label))
        return choices

    @classmethod
    def get_registered_awg_drivers(cls) -> list[str]:
        """Get list of currently registered AWG driver keys."""
        return list(cls._awg_registry.keys())

    @classmethod
    def get_registered_scope_drivers(cls) -> list[str]:
        """Get list of currently registered Scope driver keys."""
        return list(cls._scope_registry.keys())

    @classmethod
    def is_mock_awg(cls, driver_key: str) -> bool:
        """Check if a driver key corresponds to mock/simulation mode."""
        return driver_key == AWGDriver.MOCK.value

    @classmethod
    def is_mock_scope(cls, driver_key: str) -> bool:
        """Check if a driver key corresponds to mock/simulation mode."""
        return driver_key == ScopeDriver.MOCK.value

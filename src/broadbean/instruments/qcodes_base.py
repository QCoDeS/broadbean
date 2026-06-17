"""Base utilities for qcodes Station-based instruments.

This module provides common functionality for instruments that use
qcodes Station for configuration and initialization.
"""

import logging
import os
import tempfile

import yaml

logger = logging.getLogger(__name__)

# Lazy import qcodes to avoid requiring it for mock-only usage
_qcodes_station = None


def _get_station_class():
    """Lazily import qcodes Station class."""
    global _qcodes_station
    if _qcodes_station is None:
        try:
            from qcodes.station import Station

            _qcodes_station = Station
        except ImportError:
            raise ImportError(
                "qcodes is required for hardware instrument support. "
                "Install with: pip install broadbean[hardware]"
            )
    return _qcodes_station


class QCodesStationMixin:
    """Mixin providing common qcodes Station functionality.

    This mixin handles:
    - Converting config dictionaries to qcodes Station YAML format
    - Creating and managing temporary YAML files
    - Initializing qcodes Station instances
    - Cleanup of temporary resources

    Subclasses should:
    1. Define QCODES_DRIVER class attribute with the full qcodes driver path
    2. Define INSTRUMENT_NAME class attribute (e.g., "awg" or "scope")
    3. Call _init_station(config) in __init__
    4. Call _disconnect_station() in disconnect()
    """

    QCODES_DRIVER: str = None  # Override in subclass
    INSTRUMENT_NAME: str = None  # Override in subclass (e.g., "awg", "scope")

    _temp_yaml_path: str | None = None
    station = None

    def _init_station(self, config: dict):
        """Initialize qcodes Station from config dictionary.

        Creates a temporary YAML file with Station configuration and
        initializes the Station instance.

        Args:
            config: Configuration dictionary containing:
                - address: VISA address for the instrument
                - parameters: Dict of parameter configurations
        """
        if self.QCODES_DRIVER is None:
            raise ValueError(
                f"{self.__class__.__name__} must define QCODES_DRIVER class attribute"
            )
        if self.INSTRUMENT_NAME is None:
            raise ValueError(
                f"{self.__class__.__name__} must define INSTRUMENT_NAME class attribute"
            )

        Station = _get_station_class()

        yaml_content = self._config_to_station_yaml(config)
        self._temp_yaml_path = self._write_temp_yaml(yaml_content)

        logger.info(
            "Loading %s from station config (driver: %s)",
            self.INSTRUMENT_NAME,
            self.QCODES_DRIVER,
        )
        self.station = Station(config_file=self._temp_yaml_path)

    def _config_to_station_yaml(self, config: dict) -> str:
        """Convert config dictionary to qcodes Station YAML format.

        Args:
            config: Configuration dictionary containing:
                - address: VISA address for the instrument
                - parameters: Dict of parameter configurations
                - visa_timeout: VISA timeout in seconds (default: 60)

        Returns:
            YAML string suitable for qcodes Station initialization.
        """
        # Get timeout from config, default to 60 seconds
        visa_timeout = config.get("visa_timeout", 60)

        station_config = {
            "instruments": {
                self.INSTRUMENT_NAME: {
                    "type": self.QCODES_DRIVER,
                    "address": config.get("address", ""),
                    "init": {
                        "timeout": visa_timeout,
                    },
                    "parameters": config.get("parameters", {}),
                }
            }
        }
        return yaml.dump(station_config, default_flow_style=False, sort_keys=False)

    @staticmethod
    def _write_temp_yaml(yaml_content: str) -> str:
        """Write YAML content to a temporary file.

        Args:
            yaml_content: The YAML content to write.

        Returns:
            Path to the temporary YAML file.
        """
        fd, path = tempfile.mkstemp(suffix=".yaml", prefix="instrument_station_")
        try:
            with os.fdopen(fd, "w") as f:
                f.write(yaml_content)
        except Exception:
            os.close(fd)
            raise
        logger.debug("Created temporary station config: %s", path)
        return path

    def _cleanup_temp_yaml(self):
        """Remove temporary YAML file if it exists."""
        if self._temp_yaml_path and os.path.exists(self._temp_yaml_path):
            try:
                os.remove(self._temp_yaml_path)
                logger.debug(
                    "Removed temporary station config: %s", self._temp_yaml_path
                )
            except Exception as e:
                logger.warning("Failed to remove temp YAML file: %s", e)
            self._temp_yaml_path = None

    def _disconnect_station(self):
        """Close all station instruments and cleanup temporary files."""
        logger.info("Disconnecting %s", self.INSTRUMENT_NAME)

        if self.station is not None:
            try:
                self.station.close_all_registered_instruments()
            except Exception as e:
                logger.warning("Error closing station instruments: %s", e)
            self.station = None

        self._cleanup_temp_yaml()

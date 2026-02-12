"""Mock instrument implementations for simulation and testing.

This module provides mock implementations of AWG and Scope that use
shared state to simulate data passing between instruments without
requiring real hardware.
"""

import logging
import time
from typing import Tuple

import numpy as np

from broadbean.instruments.base.awg import ArbitraryWaveformGenerator
from broadbean.instruments.base.scope import Scope
from broadbean.instruments.base.mock_state import mock_state
from broadbean.instruments.registry import InstrumentRegistry

logger = logging.getLogger(__name__)


@InstrumentRegistry.register_awg("mock")
class MockAWG(ArbitraryWaveformGenerator):
    """Mock AWG implementation for simulation and testing.

    Uses the shared mock_state to store forged sequence data,
    which can then be read by MockScope to simulate the AWG->Scope
    data flow.

    Args:
        config: Configuration dictionary (ignored for mock).
        flags: Whether to use flags in sequence output (stored but not used).
        **kwargs: Additional arguments (ignored).
    """

    def __init__(self, config: dict = None, flags: bool = False, **kwargs):
        self._config = config or {}
        self.flags = flags
        logger.info("MockAWG initialized (simulation mode)")

    def upload(self, sequence):
        """Upload a sequence to the mock AWG.

        Forges the sequence and stores waveform data in mock_state.

        Args:
            sequence: Broadbean Sequence object to upload.
        """
        mock_state.set_sequence_and_forge(sequence)
        logger.info("Mock upload of sequence %s", getattr(sequence, "name", "unnamed"))

    def jump_to(self, index: int):
        """Jump to a specific sequence position.

        Args:
            index: The sequence index to jump to (1-indexed).
        """
        mock_state.jump_to_index(index)
        logger.info("Mock AWG jumped to index %d", index)

    def trigger(self):
        """Trigger the AWG to start playback."""
        mock_state.trigger_awg()
        logger.info("Mock AWG triggered")

    def trigger_segment(self, segment: int):
        """Jump to a segment and trigger.

        Args:
            segment: The segment number to jump to and trigger.
        """
        self.jump_to(segment)
        self.trigger()

    def disconnect(self):
        """Disconnect from the mock AWG.

        Does not reset mock state to allow data to persist
        between upload and trigger operations.
        """
        logger.info("Mock AWG disconnected")


@InstrumentRegistry.register_scope("mock")
class MockScope(Scope):
    """Mock Scope implementation for simulation and testing.

    Uses configuration parameters to define the simulated scope settings,
    and reads waveform data from mock_state when download() is called.

    Args:
        config: Configuration dictionary with optional parameters:
            - parameters: Dict with scope settings like:
                - horizontal.sample_rate: Sample rate in Hz
                - horizontal.record_length: Number of points per trace
        **kwargs: Additional arguments (ignored).
    """

    # Default configuration values
    DEFAULT_SAMPLE_RATE = 2.5e9
    DEFAULT_RECORD_LENGTH = 5000

    def __init__(self, config: dict = None, **kwargs):
        self._config = config or {}
        self.device = 1
        self.points_per_trace = self.DEFAULT_RECORD_LENGTH
        self.time_step = 1 / self.DEFAULT_SAMPLE_RATE

        # Configure from provided config
        self._configure()
        logger.info("MockScope initialized (simulation mode)")

    def _configure(self):
        """Configure the mock scope from the config dictionary."""
        sample_rate = self._get_parameter_value(
            "horizontal.sample_rate", self.DEFAULT_SAMPLE_RATE
        )
        record_length = self._get_parameter_value(
            "horizontal.record_length", self.DEFAULT_RECORD_LENGTH
        )

        self.points_per_trace = int(record_length)
        self.time_step = 1 / sample_rate

    def _get_parameter_value(self, param_path: str, default=None):
        """Extract a parameter value from the configuration.

        Supports both flat config_dict format and nested
        instruments.scope.parameters format.

        Args:
            param_path: Parameter path (e.g., "horizontal.sample_rate")
            default: Default value if parameter not found

        Returns:
            Parameter value or default
        """
        # Try flat parameters format first (config_dict style)
        parameters = self._config.get("parameters", {})
        if param_path in parameters:
            param = parameters[param_path]
            if isinstance(param, dict):
                return param.get("initial_value", default)
            return param

        # Try nested instruments.scope.parameters format (YAML file style)
        instruments = self._config.get("instruments", {})
        scope = instruments.get("scope", {})
        parameters = scope.get("parameters", {})
        if param_path in parameters:
            param = parameters[param_path]
            if isinstance(param, dict):
                return param.get("initial_value", default)
            return param

        return default

    def timebase(self) -> Tuple[str, np.ndarray]:
        """Get the current timebase setting of the scope.

        Returns:
            Tuple of (time_unit: str, time_axis: np.ndarray)
        """
        # Try to get time axis from mock_state first (from AWG waveform data)
        if mock_state.time_axis is not None:
            return "s", mock_state.time_axis
        elif mock_state.waveform_data is not None and len(mock_state.waveform_data) > 0:
            # Generate time axis matching the waveform data length
            num_points = len(mock_state.waveform_data[0])
            time_step = 1 / mock_state.sample_rate
            time_axis = np.arange(0, num_points) * time_step
            return "s", time_axis
        else:
            # Fall back to configured values
            time_axis = np.arange(0, self.points_per_trace) * self.time_step
            return "s", time_axis

    def single(self):
        """Set scope into single acquisition mode.

        Simulates waiting for trigger with a small delay.
        """
        time.sleep(0.1)
        logger.debug("Mock scope armed for single acquisition")

    def download(self) -> Tuple:
        """Download acquired waveforms from the mock scope.

        Returns waveform data from mock_state if available,
        otherwise generates synthetic data.

        Returns:
            Tuple of numpy arrays, one per channel.
        """
        return mock_state.get_scope_data()

    def disconnect(self):
        """Disconnect from the mock scope.

        Does not reset mock state to allow data to persist
        between operations.
        """
        logger.info("Mock scope disconnected")

"""
Shared state management for mock instruments.
This module provides a way for mock AWG and Scope to share waveform data
while maintaining compatibility with their abstract base classes.
"""

import logging
from typing import TYPE_CHECKING, Optional

import numpy as np

if TYPE_CHECKING:
    from broadbean.instruments.base.awg import ArbitraryWaveformGenerator
    from broadbean.instruments.base.scope import Scope
    from broadbean.sequence import Sequence

logger = logging.getLogger(__name__)


class MockInstrumentState:
    """
    Shared state between mock AWG and Scope instruments.

    Stores forged broadbean waveform data so that Mock_AWG uploads are
    visible to MockScope downloads. Use the module-level ``mock_state``
    instance rather than constructing new objects.
    """

    def __init__(self):
        self.waveform_data: tuple[np.ndarray, ...] | None = None
        self.time_axis: np.ndarray | None = None
        self.sample_rate: float = 25e9
        self.triggered: bool = False
        self.sequence_data: dict | None = None
        self.current_element: int = 1
        self.max_elements: int = 1
        self.awg_instance: ArbitraryWaveformGenerator | None = None
        self.scope_instance: Scope | None = None

    def set_sequence_and_forge(self, sequence: "Sequence"):
        """
        Store and forge a broadbean sequence to generate waveform data.

        Args:
            sequence: Broadbean sequence object
        """
        waveform_data = sequence.forge(includetime=True)

        self.sequence_data = waveform_data
        self.current_element = 1
        self.max_elements = len(waveform_data) if waveform_data else 1

        self.set_waveform_data(waveform_data, sequence.SR)

        logger.info(
            "Mock state: Sequence forged and stored (%d elements)",
            self.max_elements,
        )

    def set_waveform_data(self, sequence_data: dict, sample_rate: float):
        """
        Extract and store waveform data for the current element from forged sequence data.

        Expects the broadbean ``sequence.forge(includetime=True)`` output::

            {pos: {"content": {inner_pos: {"data": {ch: {"wfm": ndarray, "time": ndarray, ...}}}}}}

        Args:
            sequence_data: Dictionary from ``sequence.forge(includetime=True)``.
            sample_rate: Sample rate of the waveform.
        """
        try:
            if self.current_element not in sequence_data:
                logger.warning(
                    "Mock state: Element %d not in sequence_data (keys: %s)",
                    self.current_element,
                    list(sequence_data.keys()),
                )
                self.waveform_data = None
                self.time_axis = None
                return

            element_data = sequence_data[self.current_element]
            content = element_data.get("content", {})

            waveforms = []
            time_axis = None

            # content keys are inner-position indices (always {1: ...} for elements)
            for inner_pos in sorted(content):
                ch_data = content[inner_pos].get("data", {})
                for ch_id in sorted(ch_data):
                    channel = ch_data[ch_id]
                    if "wfm" in channel:
                        waveforms.append(channel["wfm"])
                    if "time" in channel and time_axis is None:
                        time_axis = channel["time"]

            if waveforms:
                self.waveform_data = tuple(waveforms)
                self.time_axis = time_axis
                self.sample_rate = sample_rate
                logger.info(
                    "Mock state: Extracted %d channels for element %d",
                    len(waveforms),
                    self.current_element,
                )
            else:
                logger.warning(
                    "Mock state: No waveform data found for element %d",
                    self.current_element,
                )
                self.waveform_data = None
                self.time_axis = None

        except Exception as e:
            logger.error("Mock state: Error parsing waveform data: %s", e)
            self.waveform_data = None
            self.time_axis = None

    def trigger_awg(self):
        """Mark that the AWG has been triggered and advance to next sequence element."""
        if self.sequence_data and self.sample_rate:
            self.set_waveform_data(self.sequence_data, self.sample_rate)
            loaded = self.current_element
            self.current_element = (self.current_element % self.max_elements) + 1
            logger.info(
                "Mock state: AWG triggered, element %d loaded, next: %d",
                loaded,
                self.current_element,
            )
        else:
            logger.info("Mock state: AWG triggered (no sequence data)")

        self.triggered = True

    def jump_to_index(self, index: int):
        """Jump to a specific element index in the sequence.

        Args:
            index: The sequence element index to jump to (1-based)
        """
        if self.sequence_data and self.max_elements:
            # Ensure index is within valid range (1-based indexing)
            if 1 <= index <= self.max_elements:
                self.current_element = index
                logger.info("Mock state: Jumped to element %d", index)
            else:
                logger.warning(
                    "Mock state: Invalid index %d (valid range: 1-%d)",
                    index,
                    self.max_elements,
                )
        else:
            logger.warning("Mock state: No sequence data available for jump")

    def get_scope_data(self) -> tuple[np.ndarray, np.ndarray]:
        """
        Get waveform data for scope download.

        Returns:
            Tuple of (ch1_data, ch2_data)
        """
        if self.triggered and self.waveform_data is not None:
            # Add some noise to simulate real scope acquisition
            peak_0 = np.max(np.abs(self.waveform_data[0]))
            ch1_noisy = self.waveform_data[0] + 0.01 * peak_0 * np.random.normal(
                size=self.waveform_data[0].shape
            )
            peak_1 = np.max(np.abs(self.waveform_data[1]))
            ch2_noisy = self.waveform_data[1] + 0.01 * peak_1 * np.random.normal(
                size=self.waveform_data[1].shape
            )
            logger.info("Mock state: Returning AWG waveform data with noise")
            return ch1_noisy, ch2_noisy
        else:
            # Fallback to synthetic data if no AWG data available
            logger.info("Mock state: No AWG data available, generating synthetic data")
            return self._generate_synthetic_data()

    @staticmethod
    def _generate_synthetic_data() -> tuple[np.ndarray, np.ndarray]:
        """Generate synthetic data as fallback."""
        points = 1000
        time_step = 1e-9
        t = np.arange(0, points) * time_step
        ch1 = np.sin(2 * np.pi * 5e6 * t) + 0.05 * np.random.normal(size=t.shape)
        ch2 = np.sin(2 * np.pi * 1e6 * t) + 0.05 * np.random.normal(size=t.shape)
        return ch1, ch2

    def set_instruments(self, awg_instance, scope_instance):
        """Store AWG and Scope instances for reuse between operations."""
        self.awg_instance = awg_instance
        self.scope_instance = scope_instance
        logger.info("Mock state: Instrument instances stored")

    def get_instruments(
        self,
    ) -> tuple[Optional["ArbitraryWaveformGenerator"], Optional["Scope"]]:
        """Get stored AWG and Scope instances."""
        return self.awg_instance, self.scope_instance

    def has_instruments(self):
        """Check if instrument instances are available."""
        return self.awg_instance is not None and self.scope_instance is not None

    def disconnect_instruments(self):
        """Disconnect and clear stored instrument instances."""
        if self.awg_instance is not None:
            try:
                self.awg_instance.disconnect()
                logger.info("Mock state: AWG disconnected")
            except Exception as e:
                logger.warning("Mock state: Error disconnecting AWG: %s", str(e))

        if self.scope_instance is not None:
            try:
                self.scope_instance.disconnect()
                logger.info("Mock state: Scope disconnected")
            except Exception as e:
                logger.warning("Mock state: Error disconnecting Scope: %s", str(e))

        # Clear instrument instances
        self.awg_instance = None
        self.scope_instance = None
        logger.info("Mock state: Instruments disconnected and cleared")

    def reset(self):
        """Reset the mock state."""
        self.waveform_data = None
        self.time_axis = None
        self.sample_rate = 25e9  # Reset to default sample rate
        self.triggered = False
        self.sequence_data = None
        self.current_element = 1
        self.max_elements = 1
        # Reset instrument instances
        self.awg_instance = None
        self.scope_instance = None
        logger.info("Mock state: Reset")


# Global instance for easy access
mock_state = MockInstrumentState()

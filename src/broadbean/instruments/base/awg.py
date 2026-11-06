"""Abstract base class for Arbitrary Waveform Generators (AWGs).

This module defines the ArbitraryWaveformGenerator abstract base class that
all AWG implementations must inherit from. Concrete implementations can be
found in:
- broadbean.instruments.mock.MockAWG (for simulation)
- broadbean.instruments.awg.tektronix (for Tektronix hardware)
"""

import json
import logging
from abc import ABC, abstractmethod
from pathlib import Path

from broadbean.sequence import Sequence

logger = logging.getLogger(__name__)


class ArbitraryWaveformGenerator(ABC):
    """Abstract base class for arbitrary waveform generators (AWGs).

    Defines the interface that all AWG implementations must follow.

    Methods:
        upload_sequence: Upload a waveform sequence to the AWG.
        upload_sequence_from_json: Upload a sequence from a JSON file.
        configure_upload: Configure the AWG for uploading a sequence.
        jump_to: Jump to a specific sequence index on the AWG.
        trigger: Trigger the AWG to start playback.
        trigger_segment: Jump to a segment and trigger.
        disconnect: Disconnect from the AWG instrument.
    """

    def upload_sequence_from_json(
        self,
        json_path: str | Path,
        name: str | None = None,
        calibration: dict | None = None,
    ):
        """Upload a waveform sequence from a JSON file to the AWG.

        Loads the JSON file containing sequence_data and calls upload_sequence.

        Args:
            json_path: Path to the JSON file containing the sequence data.
            name: Optional name to assign to the waveform. If not provided,
                  the filename (without extension) will be used.
            calibration: Optional calibration dictionary for amplitude LUT.

        Raises:
            FileNotFoundError: If the JSON file does not exist.
            json.JSONDecodeError: If the file contains invalid JSON.
        """
        json_path = Path(json_path)

        if not json_path.exists():
            raise FileNotFoundError(f"JSON file not found: {json_path}")

        with open(json_path) as f:
            sequence_data = json.load(f)

        # Use filename as name if not provided
        if name is None:
            name = json_path.stem

        logger.info("Loading sequence from JSON file: %s", json_path)
        self.upload_sequence(sequence_data, name, calibration)

    def upload_sequence(
        self, sequence_data: dict, name: str, calibration: dict | None = None
    ):
        """Upload a waveform in JSON format to the AWG.

        Args:
            sequence_data: The waveform data as a dictionary (sequence description).
            name: The name to assign to the waveform on the AWG.
            calibration: Optional calibration dictionary for amplitude LUT.
        """
        # Validate and sanitize sequence name - replace spaces with underscores
        if " " in name:
            original_name = name
            name = name.replace(" ", "_")
            logger.warning(
                "Sequence name '%s' contains spaces. Replaced with '%s'",
                original_name,
                name,
            )

        sequence = Sequence.sequence_from_description(sequence_data)
        # Set the sequence name from the database model
        sequence.name = name
        if calibration is not None:
            for channel_num, channel_data in calibration.items():
                input_lut = channel_data.get("input_lut", [])
                output_lut = channel_data.get("output_lut", [])
                if input_lut and output_lut:
                    sequence.setAmplitudeLUT(channel_num, input_lut, output_lut)

        self.upload(sequence)
        logger.info("Waveform %s uploaded to AWG", name)

    @abstractmethod
    def upload(self, sequence: Sequence):
        """Upload a sequence to the AWG.

        Args:
            sequence: The broadbean Sequence to upload.
        """
        raise NotImplementedError

    @abstractmethod
    def jump_to(self, index: int):
        """Jump to the specified sequence index on the AWG.

        Args:
            index: The sequence index to jump to.
        """
        raise NotImplementedError

    @abstractmethod
    def trigger(self):
        """Trigger the AWG to start playback."""
        raise NotImplementedError

    def trigger_segment(self, segment: int):
        """Trigger the AWG to play a specific segment.

        Jumps to the segment and triggers the AWG.

        Args:
            segment: The segment number to trigger.
        """
        self.jump_to(segment)
        self.trigger()

    @abstractmethod
    def disconnect(self):
        """Disconnect from the AWG instrument."""
        raise NotImplementedError

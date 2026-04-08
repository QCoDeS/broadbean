"""Tektronix AWG implementations.

This module provides AWG implementations for Tektronix arbitrary waveform
generators using qcodes Station for initialization and the standard
qcodes Tektronix driver methods.
"""

import logging

from broadbean.instruments.base.awg import ArbitraryWaveformGenerator
from broadbean.instruments.qcodes_base import QCodesStationMixin
from broadbean.instruments.registry import InstrumentRegistry
from broadbean.sequence import Sequence

logger = logging.getLogger(__name__)


class TektronixAWGBase(QCodesStationMixin, ArbitraryWaveformGenerator):
    """Base class for Tektronix AWG instruments.

    Provides common functionality for Tektronix AWGs that use:
    - upload_seqx() for uploading sequences
    - force_triggerA() for triggering
    - force_jump() for jumping to sequence positions

    Subclasses should set the QCODES_DRIVER class attribute to the
    appropriate qcodes driver path.

    Args:
        config: Configuration dictionary with:
            - address: VISA address for the AWG
            - parameters: Dict of parameter configurations (mode, sample_rate, etc.)
        flags: Whether to use flags when outputting sequence files.
        **kwargs: Additional arguments (ignored).
    """

    INSTRUMENT_NAME = "awg"
    QCODES_DRIVER: str = None  # Override in subclass

    def __init__(self, config: dict, flags: bool = False, **kwargs):
        self.flags = flags
        self._init_station(config)
        self.awg = self.station.load_awg()

        # Log some basic info
        try:
            sample_rate = self.awg.sample_rate()
            logger.info("AWG loaded - Sample rate: %s Sa/s", sample_rate)
        except Exception as e:
            logger.warning("Could not read sample rate: %s", e)

    def upload(self, sequence: Sequence):
        """Upload a sequence to the AWG using upload_seqx.

        This method:
        1. Converts the broadbean Sequence to SEQX format
        2. Uploads it to the AWG using the upload_seqx method
        3. Configures channels and starts playback

        Args:
            sequence: The broadbean Sequence to upload.
        """
        sequence_name = getattr(sequence, "name", "sequence")
        logger.info("Uploading sequence '%s' to AWG", sequence_name)

        # Generate SEQX input based on flags setting
        if self.flags:
            seqx_input = sequence.outputForSEQXFileWithFlags()
        else:
            seqx_input = sequence.outputForSEQXFile()

        # Use the qcodes driver's upload_seqx method
        # This handles: makeSEQXFile, sendSEQXFile, loadSEQXFile,
        # setSequenceTrack, channel states, and play
        self.awg.upload_seqx(seqx_input, sequence_name=sequence_name)

        logger.info("Sequence '%s' uploaded and AWG is playing", sequence_name)

    def jump_to(self, index: int):
        """Jump to a specific sequence position.

        Args:
            index: The sequence position to jump to (1-indexed, 1 to 16383).
        """
        logger.debug("Jumping to sequence position %d", index)
        self.awg.force_jump(index)

    def trigger(self):
        """Trigger the AWG using trigger A."""
        logger.debug("Triggering AWG (force_triggerA)")
        self.awg.force_triggerA()

    def trigger_segment(self, segment: int):
        """Jump to a segment and trigger.

        Args:
            segment: The segment number to jump to and trigger.
        """
        self.jump_to(segment)
        self.trigger()

    def disconnect(self):
        """Disconnect from the AWG and clean up resources."""
        self._disconnect_station()


@InstrumentRegistry.register_awg("tektronix_awg70002a")
class TektronixAWG70002A(TektronixAWGBase):
    """Tektronix AWG70002A implementation.

    Dual-channel arbitrary waveform generator with up to 25 GS/s sample rate.
    """

    QCODES_DRIVER = "qcodes.instrument_drivers.tektronix.TektronixAWG70002A"


@InstrumentRegistry.register_awg("tektronix_awg70001a")
class TektronixAWG70001A(TektronixAWGBase):
    """Tektronix AWG70001A implementation.

    Single-channel arbitrary waveform generator with up to 50 GS/s sample rate.
    """

    QCODES_DRIVER = "qcodes.instrument_drivers.tektronix.TektronixAWG70001A"

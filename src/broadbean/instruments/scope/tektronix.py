"""Tektronix Scope implementations.

This module provides Scope implementations for Tektronix oscilloscopes
using qcodes Station for initialization and the standard
qcodes Tektronix DPO driver methods.
"""

import logging

from broadbean.instruments.base.scope import Scope
from broadbean.instruments.qcodes_base import QCodesStationMixin
from broadbean.instruments.registry import InstrumentRegistry

logger = logging.getLogger(__name__)


class TektronixScopeBase(QCodesStationMixin, Scope):
    """Base class for Tektronix scope instruments.

    Provides common functionality for Tektronix scopes that use:
    - single() for single acquisition mode
    - download_waveforms() for downloading acquired waveforms
    - get_timebase() for getting time axis information

    Subclasses should set the QCODES_DRIVER class attribute to the
    appropriate qcodes driver path.

    Args:
        config: Configuration dictionary with:
            - address: VISA address for the scope
            - parameters: Dict of parameter configurations
        **kwargs: Additional arguments (ignored).
    """

    INSTRUMENT_NAME = "scope"
    QCODES_DRIVER: str = None  # Override in subclass

    def __init__(self, config: dict, **kwargs):
        self._init_station(config)
        self.scope = self.station.load_scope(update_snapshot=False)
        logger.info("Scope loaded successfully")

    def single(self):
        """Set scope into single acquisition mode and wait for triggered acquisition.

        This uses the qcodes driver's single() method which:
        1. Sets stop_after to "SEQUENCE"
        2. Sets acquisition state to "RUN"
        3. Waits for trigger ready state
        """
        logger.debug("Setting scope to single acquisition mode")
        self.scope.single()
        logger.debug("Scope ready for triggered acquisition")

    def download(self) -> tuple:
        """Download acquired waveforms from enabled channels.

        Returns:
            Tuple of numpy arrays, one per enabled channel.
        """
        logger.debug("Downloading waveforms from scope")
        waveforms = self.scope.download_waveforms()
        logger.info("Downloaded %d waveforms", len(waveforms))
        return waveforms

    def timebase(self) -> tuple[str, any]:
        """Get the timebase information from the scope.

        Returns:
            Tuple of (time_unit: str, time_axis: np.ndarray)
        """
        logger.debug("Getting timebase from scope")
        time_unit, time_axis = self.scope.get_timebase()
        return time_unit, time_axis

    def disconnect(self):
        """Disconnect from the scope and clean up resources."""
        self._disconnect_station()


@InstrumentRegistry.register_scope("tektronix_dpo70000")
class TektronixDPO70000(TektronixScopeBase):
    """Tektronix DPO70000 series oscilloscope implementation.

    High-performance digital phosphor oscilloscope series with
    bandwidths up to 70 GHz.
    """

    QCODES_DRIVER = "qcodes.instrument_drivers.tektronix.TektronixDPO70000"


@InstrumentRegistry.register_scope("tektronix_dpo7200")
class TektronixDPO7200(TektronixScopeBase):
    """Tektronix DPO7200 series oscilloscope implementation.

    Digital phosphor oscilloscope series with bandwidths up to 3.5 GHz.
    """

    QCODES_DRIVER = "qcodes.instrument_drivers.tektronix.DPO7200xx"

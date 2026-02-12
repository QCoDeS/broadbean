"""Abstract base class for Oscilloscope instruments.

This module defines the Scope abstract base class that all oscilloscope
implementations must inherit from. Concrete implementations can be found in:
- broadbean.instruments.mock.MockScope (for simulation)
- broadbean.instruments.scope.tektronix (for Tektronix hardware)
"""

import logging
from abc import ABC, abstractmethod
from typing import Tuple

logger = logging.getLogger(__name__)


class Scope(ABC):
    """Abstract base class for oscilloscope instruments.

    Defines the interface that all Scope implementations must follow.

    Methods:
        timebase: Get the current timebase setting of the scope.
        single: Set the scope to single acquisition mode.
        download: Download the acquired data from the scope.
        disconnect: Disconnect from the scope instrument.
    """

    @abstractmethod
    def timebase(self) -> Tuple[str, any]:
        """Get the current timebase setting of the scope.

        Returns:
            Tuple of (time_unit: str, time_axis: np.ndarray)
        """
        raise NotImplementedError

    @abstractmethod
    def single(self):
        """Set the scope to single acquisition mode.

        Arms the scope and waits for a trigger event.
        """
        raise NotImplementedError

    @abstractmethod
    def download(self) -> Tuple:
        """Download the acquired data from the scope.

        Returns:
            Tuple of numpy arrays, one per enabled channel.
        """
        raise NotImplementedError

    @abstractmethod
    def disconnect(self):
        """Disconnect from the scope instrument."""
        raise NotImplementedError

# This file contains the Element definition

from typing import Union, Dict, List
from copy import deepcopy

import numpy as np

from broadbean.segment import Segment


class ElementDurationError(Exception):
    pass


class Element:
    """
    Object representing an element. An element is a collection of waves that
    are to be run simultaneously. The element consists of a number of channels
    that are then each filled with anything of the appropriate length.
    """
    def __init__(self, segments={}):
        self.segments = segments

    @property
    def duration(self):
        """
        Returns the duration in seconds of the element, if said duration is
        well-defined. Else raises an error.
        """
        durations = set(s.get('duration') for _, s in self._segments.items())
        if len(durations) != 1:
            raise ElementDurationError
        return durations.pop()

    def copy(self):
        return Element(deepcopy(self.segments))

    # TODO: add methods/operators for stacking, concatenation, equality

# This file contains the Element definition

from typing import Union, Dict, List
from copy import deepcopy, copy

import numpy as np

from broadbean.segment import Segment, ContextDict
from broadbean.transformations import get_transformed_context
from .types import RoutesDictType, ForgedSequenceType, ContextDict

ChannelIDType = Union[int,str]

class ElementDurationError(Exception):
    pass


class Element:
    """
    Object representing an element. An element is a collection of waves that
    are to be run simultaneously. The element consists of a number of channels
    that are then each filled with anything of the appropriate length.
    """
    def __init__(self, segments:Dict[ChannelIDType, Segment]={},
                 sequencing:Dict[str, int]={},
                 local_context={},
                 transformation:callable={}):
        self.segments = segments
        self.sequencing = sequencing
        self.local_context = local_context
        self._transformation = transformation
        # make sequencing options kwargs
        # define jump target maybe as element reference that gets dereferenced in sequence?
        # self._sequencing[pos] = {'twait': wait, 'nrep': nreps,
        #                          'jump_target': jump, 'goto': goto,
        #                          'jump_input': 0}

    def get_duration(self, **context):
        """
        Returns the duration in seconds of the element, if said duration is
        well-defined. Else raises an error.
        """

        durations = set(s.get('duration', **context) for _, s in self.segments.items())
        if len(durations) != 1:
            raise ElementDurationError
        return durations.pop()


    def __copy__(self):
        return Element(deepcopy(self.segments),
                       deepcopy(self.sequencing),
                       transformation=self._transformation)

    # I think this should go into the main forge function. There is no point of forging an element outside of a sequence. This is different for a Segment.
    def forge(self,
              SR,
              context: ContextDict,
              routes: RoutesDictType=None,
              instrument_name: str=None,
              meta_data_only: bool=False):
        """
        forge and apply routing to a forged sequence.
        This function forges the element and returns a dictionary of the channel data
        where the keys are chosen according to the rules defined
        in `routes` for the given instrument `instrument`.
        Channels that are not defined in the routes for the chosen instrument will
        not be contained in the returned dictionary.
            routes: The dictionary defining the routes.
                E.g. {'MyChannel': ('MyAWG', '1M1')}
            instrument: An instrument to narrow down the search.
                If `None` the result matching any kind of instrument is returned.
        """
        # first apply local context
        context = copy(context)
        context.update(self.local_context)
        # then apply transformation
        context = get_transformed_context(context, self._transformation)

        # the following is all routing
        ret = {}
        for channel_id, segment in self.segments.items():
            # no routing, catch all instruments
            if routes is None:
                selected_instrument = None
                physical_channel = channel_id
            else:
                try:
                    r = routes[channel_id]
                except KeyError:
                    # TODO: handle this situation:
                    # the virtual channel as specified in the sequence is not
                    # accounted for in the routing.
                    # -> soft or hard error/warning. What gain is there to do
                    # this intentionally?
                    continue
                if type(r) is tuple:
                    selected_instrument = r[0]
                    physical_channel = r[1]
                else:
                    selected_instrument = None
                    physical_channel = r
            if (instrument_name == None or
                selected_instrument == None or
                selected_instrument == instrument_name):
                ret[physical_channel] = segment.forge(SR,
                                                      meta_data_only=meta_data_only,
                                                      **context)
        return ret


    # TODO: add methods/operators for stacking, concatenation, equality

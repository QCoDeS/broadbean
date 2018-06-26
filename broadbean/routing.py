from typing import Union, Dict, Tuple
from copy import copy

from qcodes.instrument.base import InstrumentBase
from broadbean.tools import forged_sequence_dict_to_list
from broadbean.sequence import ForgedSequenceType
# from broadbean.element import ChannelIDType

ChannelIDType = Union[int,str]
#PhysicalChannelType describes the identifier type for the pyhsical output
# channel of a signal generating device. E.g. '1M1' for marker 1 of channel 1
# of the AWG5014.
PhysicalChannelType = Union[str, int]

# The RoutesDictType describes a dictionary for routing abstract channels in
# Broadbean to real channels on instruments.
# e.g. {'MyChannel': ('MyAWG', '1M1')}.
# If no tuple is given as a value but rather a `PhysicalChannelType`, the
# entry is interpreted as *catch all* and is routed to all devices that expose
# such a channel.
RoutesDictType=Dict[ChannelIDType,
                    Union[PhysicalChannelType,
                          Tuple[str, PhysicalChannelType]]]


def route(seq: ForgedSequenceType,
          routes: RoutesDictType,
          instrument: InstrumentBase=None) -> ForgedSequenceType:
    """
    Apply routing to a forged sequence.
    This function takes the forged sequence `seq` and returns a forged sequence
    where the ChannelIDs have been replaced by according to the rules defined
    in `routes` for the given instrument `instrument`.
    Channels that are not defined in the routes for the chosen instrument will
    not be contained in the returned forged sequence.
    The returned object contains references to the original object, so that
    the data is not copied. The returned object has to be handled as
    read-only because some elements can only be copied by value. (Actually
    only the `type` entry)
        seq: input sequence
        routes: The dictionary defining the routes.
            E.g. {'MyChannel': ('MyAWG', '1M1')}
        instrument: An instrument to narrow down the search.
            If `None` the result matching any kind of instrument is returned.
    """
    # compatibility
    seq = forged_sequence_dict_to_list(seq)
    for elem in seq:
        for subelem in elem['content']:
            # to rename the keys of a dictionary we need to create a new one
            new_dd = {}
            for k, v in subelem['data'].items():
                try:
                    r = routes[k]
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
                if (instrument == None or
                    selected_instrument == None or
                    selected_instrument == instrument.name):
                    new_dd[physical_channel] = v
            subelem['data'] = new_dd
    return seq

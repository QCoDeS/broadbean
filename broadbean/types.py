import numpy as np
from schema import Schema, Or, Optional
from typing import Union, Any, Dict, Tuple

# schema validation types:

_channel_dict = {Or(str, int): np.ndarray}
_sequencing_dict = {Optional(str): int}
_element_dict = {
    'data': Or(
            [
                {'data': _channel_dict,
                 'sequencing': _sequencing_dict}
            ],
            _channel_dict
            ),
    'sequencing': _sequencing_dict
}
forged_element_schema = Schema(_element_dict)
fs_schema = Schema([_element_dict])

fs_schema_old = Schema({int: {'type': Or('subsequence', 'element'),
                          'content': {int: {'data': {Or(str, int): {str: np.ndarray}},
                                            Optional('sequencing'): {Optional(str):
                                                                    int}}},
                          'sequencing': {Optional(str): int}}})


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

# Until I can be bothered
ForgedSequenceType = Any
# ForgedSequenceType = Dict[int, Dict[str, Union[str, Dict[]]]]

Number = Union[float, int, None]
Symbol = str
ContextDict = Dict[Symbol, Number]

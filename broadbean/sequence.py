import logging
import numpy as np
from typing import List, Dict, Any
from schema import Schema, Or, Optional
from .element import Element
from .segment import ContextDict


log = logging.getLogger(__name__)

fs_schema = Schema({int: {'type': Or('subsequence', 'element'),
                          'content': {int: {'data': {Or(str, int): {str: np.ndarray}},
                                            Optional('sequencing'): {Optional(str):
                                                                    int}}},
                          'sequencing': {Optional(str): int}}})


# Until I can be bothered
ForgedSequenceType = Any
# ForgedSequenceType = Dict[int, Dict[str, Union[str, Dict[]]]]

class Sequence:
    """
    Sequence object
    thin wrapper around a list
    how is this different from a list?-> has sequencing options
    """

    def __init__(self, elements:List[Element]=[]) -> None:
        self.elements = elements
        # if this is a subsequence
        self.sequencing = {}

    def forge(self, SR, context: ContextDict={}) -> Dict[int, Dict]:
        output: Dict[int, Dict] = {}
        for ie, elem in enumerate(self.elements):
            item = {}
            item['sequencing'] = elem.sequencing
            item['content'] = {}
            if isinstance(elem, Sequence):
                item['type'] = 'subsequence'
                for ies, subelem in enumerate(elem.elements):
                    item['content'][ise] = {
                        'data': subelem.forge(SR, context),
                        'sequencing': subelem.sequencing}
            elif isinstance(elem, Element):
                item['type'] = 'element'
                item['content'][0] = {'data': elem.forge(SR, context)}
            output[ie] = item
        return output

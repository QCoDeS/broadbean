import logging
import numpy as np
from typing import List, Dict, Any
from .element import Element
from .segment import ContextDict


log = logging.getLogger(__name__)

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
        output: ForgedSequenceType = []
        for elem in self.elements:
            if isinstance(elem, Sequence):
                data = [{'data': subelem.forge(SR, context),
                         'sequencing': subelem.sequencing}
                         for subelem in elem.elements]
            else:
                data = elem.forge(SR, context)
            output.append({'data': data,
                           'sequencing': elem.sequencing})
        return output

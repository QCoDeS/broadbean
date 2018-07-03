import logging
import numpy as np
from typing import List, Dict, Any, Union
from .element import Element
from .types import RoutesDictType, ForgedSequenceType, ContextDict


log = logging.getLogger(__name__)


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

    def forge(self,
              SR: Union[float, int],
              context: ContextDict={},
              routes: RoutesDictType=None,
              instrument_name: str=None) -> ForgedSequenceType:
        output: ForgedSequenceType = []
        forge_element = lambda elem: elem.forge(SR, context,
                                                routes, instrument_name)
        for elem in self.elements:
            if isinstance(elem, Sequence):
                data = [{'data': forge_element(subelem),
                         'sequencing': subelem.sequencing}
                         for subelem in elem.elements]
            else:
                data = forge_element(elem)
            output.append({'data': data,
                           'sequencing': elem.sequencing})
        return output


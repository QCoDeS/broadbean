# High-level tool for sequence building and manipulation
#

import numpy as np
import logging
from copy import copy

from broadbean.sequence import Sequence

log = logging.getLogger(__name__)


def forged_sequence_dict_to_list(seq):
    """converts the dictionary style forged sequence into a list style one.
    This function is intended to be used to help in the process of converting
    over to the new structure of the forged sequence definition with lists
    instead of dictionaries

    This function does not copy the data but retains references to the
    data. This is not true for the `type` element. It therefore should
    only be used to read from it and not for writing to it.
    """
    # top level transformation (no subsequnces)
    length = len(seq.keys())
    list_of_elements = []
    for index in range(length):
        try:
            # this copy call is needed so that in the next step where the
            # value of 'content' is changed from a dictionary to a list
            # only the new object is going to be changed not the old one with
            # dictionary structure
            # In general one could say we want to copy all, except for the
            # lowest level values, i.e. we want to change the structure but
            # not the content
            list_of_elements.append(copy(seq[index]))
        except KeyError:
            log.error(f'Error converting forged sequence dict to list: The '
                      f'sequence seems to be sparse. The element no. {index} '
                      f'does not exist int the dictionary, yet there are '
                      f'{length} elements.')
    return_val = list_of_elements

    # subsequences
    for i_elem, elem in enumerate(return_val):
        dict_content = elem['content']
        length = len(dict_content.keys())
        list_of_elements = []
        for index in range(length):
            try:
                # now this `copy` call here is a tricky one:
                # It makes most sense to copy this dictionary, as its structure
                # is already fully determined (`data` and `sequencing` as
                # keys) and its values are purely references.
                # when using :meth:`broadbean.routing.route` the value of
                # `data` is changed (namely by replacing it with another dict).
                # if we don't copy here also the original dict will be changed
                list_of_elements.append(copy(dict_content[index]))
            except KeyError:
                log.error(f'Error converting forged sequence dict to list: '
                          f'The subsequence seems to be sparse (Element no. '
                          f'{i_elem}). The subelement no. {index} does not '
                          f'exist int the dictionary, yet there are {length} '
                          f'elements.')
        elem['content'] = list_of_elements
    return return_val

# High-level tool for sequence building and manipulation
#

import numpy as np
import logging
from copy import copy

from .sequence import Sequence
from .element import Element

log = logging.getLogger(__name__)

# tools operating on the forged sequence
def is_subsequence(forged_element) -> bool:
    return isinstance(forged_element['data'], list)

def get_element_channel_ids(forged_element):
    if is_subsequence(forged_element):
        raise NotImplementedError()
    else:
        return forged_element['data'].keys()

def get_element_duration(forged_element, channel_id=None):
    if is_subsequence(forged_element):
        raise NotImplementedError()
    else:
        if channel_id == None:
            channel_id = get_element_channel_ids(forged_element)[0]
        return forged_element['data'][channel_id].size

# checks
def check_element_duration_consistent(forged_element):
    if is_subsequence(forged_element):
        raise NotImplementedError()
    durations = [get_element_duration(forged_element, elem_id)
                 for elem_id
                 in get_element_channel_ids(forged_element)]
    assert len(set(durations)) == 1

def check_sequence_duration_consistent(forged_sequence):
    for elem in forged_sequence:
        check_element_duration_consistent(elem)

def forged_sequence_dict_to_list(seq):
    """converts the dictionary style forged sequence into a list style one.
    This function is intended to be used to help in the process of converting
    over to the new structure of the forged sequence definition with lists
    instead of dictionaries

    This function does not copy the data but retains references to the
    data. This is not true for the `type` element. It therefore should
    only be used to read from it and not for writing to it.
    """
    # don't do anything if it is applied to an already converted sequence
    if type(seq) is list:
        return seq
    # top level transformation (no subsequnces)
    length = len(seq.keys())
    # acommodate for 1 and 0 based indeces
    min_val = min(seq.keys())
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
            list_of_elements.append(copy(seq[index + min_val]))
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
        # acommodate for 1 and 0 based indeces
        min_val = min(seq.keys())
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
                list_of_elements.append(copy(dict_content[min_val + index]))
            except KeyError:
                log.error(f'Error converting forged sequence dict to list: '
                          f'The subsequence seems to be sparse (Element no. '
                          f'{i_elem}). The subelement no. {index} does not '
                          f'exist int the dictionary, yet there are {length} '
                          f'elements.')
        elem['content'] = list_of_elements
    return return_val

def forged_sequence_list_to_dict(seq):
    if type(seq) is dict:
        return seq
    ret = {}
    for i, elem in enumerate(seq):
        elemdict = {}
        if is_subsequence(elem):
            subdict = {}
            for subi, subelem in enumerate(elem['data']):
                subdict[subi] = subelem
            elemdict['type'] = 'subsequence'
            elemdict['content'] = subdict
        else:
            elemdict['type'] = 'element'
            elemdict['content'] = {1: {'data': {'wfm':elem['data']}}}
        elemdict['sequencing'] = elem['sequencing']
        ret[i] = elemdict
    return ret

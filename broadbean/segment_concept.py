import numpy as np
from copy import copy, deepcopy

from typing import Union, Dict, List
Number = Union[float, int]
Property =  Union[Number, str, None]
PropertyDict = Dict[str, Property]
ContextDict = Dict[str, Number]
TimeType = np.ndarray

class Segment:
    def __init__(self, **properties: PropertyDict):
        if 'duration' not in properties:
            raise ValueError('You must specify a duration for a segment. It may be "None" if it is dynamically determined.')
        self._properties = properties


    def forge(self,
              SR: Number,
              **context_and_values: ContextDict) -> np.ndarray:
        raise NotImplementedError

    def get_property(self,
                     name: str,
                     **context_and_values: ContextDict) -> Number:
        # it might be prone to errors to put context and values together into one dict
        k, v = name, self._properties[name]
        if v is None:
            # item is defined as by_value
            if k not in context_and_values:
                raise ValueError('Property {}:{} has to be supplied as a value.'.format(k, v))
            return context_and_values[k]
        elif isinstance(v, str):  # add possibility for escaping strings here
            # item is defined as by_context
            # make sure it is not also defined as value
            if k in context_and_values:
                raise ValueError('Property {}:{} is already speciefied in the context and cannot also be specified as a value.'.format(k, v))
            return context_and_values[v]
        else:
            # item has a fixed value
            return v

    def get_all_properties(self,
                       **context_and_values: ContextDict) -> Dict[str, Number]:
        return {k:self.get_property(k, **context_and_values) for k,v in self._properties.items()}
        


class FunctionSegment(Segment):
    def __init__(self,
                 function: callable,
                 duration: Number,
                 **function_arguments: PropertyDict) -> None:
        # check if compatible with function footprint and has a duration
        super().__init__(**function_arguments, duration=duration)
        self._function = function

    def forge(self,
              SR: Number,
              **context_and_values: ContextDict) -> np.ndarray:
        # retrieve values valid in context
        properties = deepcopy(self.get_all_properties(**context_and_values))
        duration = properties.pop('duration')

        # check minimum length
        int_dur = int(duration*SR)
        if int_dur < 2:
            raise ValueError('Cannot forge segment; forging must result in at'
                             ' least two points, but this segment has only '
                             f'{int_dur}')
        # create time array
        time_array = np.linspace(0, duration, int_dur, endpoint=False)
        properties.update({'time': time_array})

        return self._function(**properties)


class GroupSegment(Segment):
# TODO: prevent recursive nesting of segments
    def __init__(self,
                 *segments: List['Segment'],
                 **properties: PropertyDict) -> None:
        # propterties is basically duration
        super().__init__(**properties)
        self._segments = segments

    def get_property(self,
                     name: str,
                     **context_and_values: ContextDict) -> Number:
        if name == 'duration':
            n_expandable_children = sum(1 for s in self._segments if s._properties[name] is None)
            if n_expandable_children == 0:
                # duration fixed by children
                duration = sum(s.get_property(name, **context_and_values) for s in self._segments)
                return super().get_property(name, **context_and_values, duration=duration)
            elif n_expandable_children > 1:
                # this case is not supported
                raise RuntimeError('only one child segment can be expandable')
            else:
                # duration fixed by group segment
                return super().get_property(name, **context_and_values)

    def forge(self,
              SR: Number,
              **context_and_values: ContextDict) -> np.ndarray:
        # getting here means that there is exactly one or none child segment with undetermined duration

        # TODO: Make this faster once everything works
        return_array = np.zeros(())
        # find missing duration
        missing_duration = self.get_property('duration',
                                             **context_and_values) -  sum(
                                    s.get_property('duration', **context_and_values) for s in self._segments if s._properties['duration'] is not None)
        for s in self._segments:
            if s._properties['duration'] is None:
                # some unecessary copying here
                return_array = np.append(return_array, s.forge(SR, **context_and_values, duration=missing_duration))
            else:
                # some unecessary copying here
                nreturn_array = np.append(return_array, s.forge(SR, **context_and_values))
        return return_array

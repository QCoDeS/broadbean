import numpy as np
from copy import copy, deepcopy

from typing import Union, Dict, List
Number = Union[float, int]
Property =  Union[Number, str, None]
PropertyDict = Dict[str, Property]
ContextDict = Dict[str, Number]
TimeType = np.ndarray

class _Expandable:
    pass

expandable = _Expandable()

class Segment:
    def __init__(self, duration, **properties: PropertyDict):
        properties['duration'] = duration
        self._properties = properties


    def forge(self,
              SR: Number,
              duration = None,
              **context: ContextDict) -> np.ndarray:
        raise NotImplementedError

    def get(self,
            name: str,
            **context: ContextDict) -> Number:
        # it might be prone to errors to put context and values together into one dict
        value_or_symbol = self._properties[name]
        if isinstance(value_or_symbol, str):  # add possibility for escaping strings here
            # is symbol
            return context[value_or_symbol]
        else:
            # is value
            return value_or_symbol

    def get_all_properties(self,
                           **context: ContextDict) -> Dict[str, Number]:
        return {k:self.get(k, **context) for k,v in self._properties.items()}

    @property
    def is_expandable(self):
        return self._properties['duration'] == expandable

    def _safe_get_duration(self, duration, **context):
        if self.is_expandable:
            # duration must be supplied explicitly
            if duration is None:
                raise ValueError('Must supply duration')
            return duration
        else:
            # duration fixed by segment
            if duration is not None:
                raise ValueError('Duration cannot be overridden.')
            own_duration = self.get('duration', **context)
            if own_duration is None:
                raise ValueError('Must supply duration')
            return self.get('duration', **context)



class FunctionSegment(Segment):
    def __init__(self,
                 function: callable,
                 duration: Number=None,
                 **function_arguments: PropertyDict) -> None:
        # check if compatible with function footprint and has a duration
        if duration is None:
            raise ValueError('Must supply a duration to a FunctionSegment')
        super().__init__(duration=duration, **function_arguments)
        self._function = function

    def forge(self,
              SR: Number,
              duration=None,
              **context: ContextDict) -> np.ndarray:
        duration = self._safe_get_duration(duration, **context)

        # check minimum length
        int_dur = int(duration*SR)
        if int_dur < 2:
            raise ValueError('Cannot forge segment; forging must result in at'
                             ' least two points, but this segment has only '
                             f'{int_dur}')
        # create time array
        time_array = np.linspace(0, duration, int_dur, endpoint=False)
        kwargs = self.get_all_properties(**context)
        kwargs.pop('duration')
        return self._function(time=time_array,
                              **kwargs)


class GroupSegment(Segment):
# TODO: prevent recursive nesting of segments
    def __init__(self,
                 *segments: List['Segment'],
                 duration = None,
                 **properties: PropertyDict) -> None:
        super().__init__(duration=duration, **properties)
        self._segments = segments

    def get(self,
            name: str,
            **context: ContextDict) -> Number:
        if name == 'duration':
            n_expandable_children = sum(1 for s in self._segments if s.is_expandable)
            if n_expandable_children == 0:
                # duration fixed by children
                if self._properties['duration'] is not None:
                    raise RuntimeError('duration has been specified for group, but all child elements also have a fixed duration.')
                return sum(s.get(name, **context) for s in self._segments)
            elif n_expandable_children > 1:
                # this case is not supported
                raise RuntimeError('only one child segment can be expandable')
            else:
                # has exactly one expandable child
                # duration may be fixed, expandable, or symbol
                return super().get(name, **context)
        else:
            return super().get(name, **context)

    def forge(self,
              SR: Number,
              duration=None,
              **context: ContextDict) -> np.ndarray:
        # getting here means that there is exactly one or none child segment with undetermined duration

        # checks if duration is supplyable by an argument, fails if not
        own_duration = self._safe_get_duration(duration, **context)
    
        # from IPython.core.debugger import set_trace
        # set_trace()

        # TODO: Make this faster once everything works
        return_array = np.array([])
        # find missing duration
        missing_duration = own_duration - sum(s.get('duration', **context) for s in self._segments if not s.is_expandable)
        if missing_duration < 0:
            raise RuntimeError('The expandable element in this group cannot have negative length.')
        for s in self._segments:
            if s.is_expandable:
                # some unecessary copying here
                return_array = np.append(return_array, s.forge(SR, **context, duration=missing_duration))
            else:
                # some unecessary copying here
                return_array = np.append(return_array, s.forge(SR, **context))
        return return_array

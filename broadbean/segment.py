import numpy as np
from copy import copy, deepcopy

from typing import Union, Dict, List

from .transformations import get_transformed_context

Number = Union[float, int, None]
Property =  Union[Number, str, None]
PropertyDict = Dict[str, Property]
ContextDict = Dict[str, Number]
TimeType = np.ndarray

def in_context(obj, **context:ContextDict) -> Union['Segment', 'GroupSegment', 'Element']:
        ret = copy(obj)
        ret.local_context = context
        return ret

class Symbol:
    def __init__(self, value):
        self.value = value

    def get(self, context):
        if isinstance(self.value, str):  # add possibility for escaping strings here
            # is symbol
            return context[self.value]
        else:
            # is value
            return self.value


class _BaseSegment:
    def __init__(self,
                 duration: Union[Number, str]=None,
                 **properties: PropertyDict):
        properties['duration'] = duration
        self._properties = properties

    def forge(self,
              SR: Number,
              duration=None,
              **context: ContextDict) -> np.ndarray:
        raise NotImplementedError

    def get(self,
            name: str,
            **context: ContextDict) -> Number:
        # it might be prone to errors to put context and values together into
        # one dict
        value_or_symbol = self._properties[name]
        if isinstance(value_or_symbol, str): # add possibility for escaping strings here
            # is symbol
            return context[value_or_symbol]
        else:
            # is value
            return value_or_symbol

    def get_all_properties(self,
                           **context: ContextDict) -> Dict[str, Number]:
        return {k: self.get(k, **context)
                for k, v in self._properties.items()}

    #def apply_context(self, **context: ContextDict) -> None:
    #     context = copy(context)
    #     for prop_name, prop_value in self._properties.items():
    #         if isinstance(prop_value, str) and prop_value in context:
    #             self._properties[prop_name] = context.pop(prop_value)

    #     if context: # is not empty
    #         # TODO: write better warning
    #         raise RuntimeWarning('Could not fully apply context')

    # convenience functions
    def _property_list(self):
        output = ''
        for name, value in self._properties.items():
            if isinstance(value, str):
                valstr = f"'{value}'"
            else:
                valstr = f"{value}"
            output += f'{name}={valstr}, '
        output = output[:-2]
        return output

    def __repr__(self) -> str:
        output = '_BaseSegment( '
        output += self._property_list()
        output += ')'
        return output


class Segment(_BaseSegment):
    def __init__(self,
                 function: callable,
                 duration: Union[Number, str]=None,
                 **function_arguments: ContextDict) -> None:
        # TODO: check if compatible with function footprint and has a duration
        super().__init__(duration=duration,
                         **function_arguments)
        self._function = function

    def forge(self,
              SR: Number,
              **context) -> np.ndarray:
        duration = self.get('duration', **context)

        # check minimum length
        int_dur = int(duration*SR)
        if int_dur < 2:
            # get rid of this restriction, which is totally unecessary
            raise ValueError('Cannot forge segment; forging must result in at'
                             ' least two points, but this segment has only '
                             f'{int_dur}')
        # create time array
        time_array = np.linspace(0, duration, int_dur, endpoint=False)
        kwargs = self.get_all_properties(**context)
        kwargs.pop('duration')
        return self._function(time=time_array,
                              **kwargs)

    # convenience functions
    def __repr__(self) -> str:
        output = f'Segment({self._function.__name__}, '
        output += self._property_list()
        output += ')'
        return output


class SegmentGroup(_BaseSegment):

    def __init__(self,
                 *segments: List[Segment],
                 duration,
                 transformation=None) -> None:
        super().__init__(duration=duration)
        self._transformation = transformation
        self._segments = segments

    def forge(self,
              SR: Number,
              **context: ContextDict) -> np.ndarray:
        new_context = get_transformed_context(context, self._transformation)
        # this is the simples implemenation without any time constraints
        return_array = np.array([])
        for s in self._segments:
            return_array = np.append(return_array, s.forge(SR, **new_context))
        return return_array

    # def apply_context(self, **context: ContextDict) -> None:
    #     for s in self._segments:
    #         s.apply_context(**context)

    def get(self,
            name: str,
            **context: ContextDict) -> Number:
        return super().get(name, **self._transformation(context))

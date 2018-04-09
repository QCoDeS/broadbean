# The module defining the segment object
#
#

from typing import Callable, Dict, Union
from inspect import signature

import numpy as np

# types for good hinting
Number = Union[float, int]
ArgsDict = Dict[str, Union[Number, str, None]]


def validate_function_and_args_dict(func: Callable,
                                    args_dict: ArgsDict) -> None:
    """
    Validate whether a function can be used in a segment
    to generate an array and validate that the args_dict matches
    the function.

    The function must have the two arguments dur and SR and can
    have as many other arguments as it will and the args_dict must
    specify all these additional arguments
    """
    sig = signature(func)
    argnames = [an for an in sig.parameters]

    try:
        argnames.remove('time')
    except ValueError:
            raise ValueError('Function invalid, must have the'
                             ' argument "time".')

    _dur = args_dict.pop('duration')

    if not set(argnames) == set(args_dict.keys()):
        raise ValueError('Invalid args_dict. args_dict specifies '
                         f'{set(args_dict.keys())}, but the function '
                         f'expects {set(argnames)}.')

    args_dict.update({'duration': _dur})


class Segment:
    """
    The smallest broadbean particle
    """

    def __init__(self, function: Callable, **kwargs) -> None:
        """
        Args:
            function: the function that, when fed with the kwargs
                (minus 'duration', plus 'time') returns an array
            kwargs: the parameters for the function except 'time' and
                also the segment duration
        """

        validate_function_and_args_dict(function, kwargs)

        self.function = function
        self._duration = kwargs.pop('duration')
        self.args_dict = kwargs

        symbols = {v: k for (k, v) in self.args_dict.items()
                   if isinstance(v, str)}
        self._symbols = symbols

    @property
    def duration(self) -> Union[str, Number, None]:
        return self._duration

    @property
    def symbols(self) -> Dict[str, str]:
        return self._symbols

    def forge(self, SR: int, **kwargs) -> np.ndarray:
        """
        Forge the segment into an array. Keyword arguments can
        contain a duration (must be called 'duration') and should otherwise
        specify values for any symbols in the segment

        Args:
            SR: The sample rate (Sa/s)
        """

        duration = None

        if 'duration' in kwargs.keys():
            duration = kwargs.pop('duration')
            # after this pop, only symbols are in the kwargs
        elif self.duration:
            duration = self.duration

        if not duration:
            raise ValueError('Cannot forge segment, no duration specified')

        if not set(self._symbols) == set(kwargs.keys()):
            raise ValueError('Cannot forge segment, incorrect symbol '
                             f'values provided. Got {set(kwargs.keys())},'
                             f' expected {set(self._symbols)}.')

        args_dict = self.args_dict.copy()
        args_dict.update({self._symbols[s]: kwargs[s] for s in kwargs.keys()})

        int_dur = int(duration*SR)
        if int_dur < 2:
            raise ValueError('Cannot forge segment; forging must result in at'
                             ' least two points, but this segment has only '
                             f'{int_dur}')
        time_array = np.linspace(0, duration, int_dur, endpoint=False)

        args_dict.update({'time': time_array})

        array = self.function(**args_dict)

        return array

    def __repr__(self) -> str:
        output = f'Segment({self.function.__name__},\n'
        for name, value in self.args_dict.items():
            if isinstance(str, value):
                valstr = f"'{value}'"
            else:
                valstr = f"{value}"
            output += f'{name}={valstr}\n'
        output += f'duration={self.duration})'
        return output

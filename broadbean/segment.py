# The module defining the segment object
#
#

from typing import Callable, Dict, Union, Optional
from numbers import Number
from inspect import signature
from functools import wraps

import numpy as np

ArgsDict = Dict[str, Union[Number, str]]


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

    if 'dur' not in argnames:
        raise ValueError('Function invalid, must have the argument "dur".')
    if 'SR' not in argnames:
        raise ValueError('Function invalid, must have the argument "SR".')

    argnames.remove('SR')
    argnames.remove('dur')

    if not set(argnames) == set(args_dict.keys()):
        raise ValueError('Invalid args_dict. args_dict specifies '
                         f'{set(arg_dict.keys())}, but the function '
                         f'expects {set(argnames)}.')


class Segment:
    """
    The smallest broadbean particle
    """

    def __init__(self, name: str, function: Callable,
                 args_dict: ArgsDict,
                 duration: Optional[float]=None) -> None:
        """
        Args:
            name: the name of the segment
            function: the function that, when fed with the args from the
                args_dict plus an 'SR' and a 'dur', returns the signal array
            args_dict: dictionary with {arg_name: arg_value} items.
                The args are the arguments to the function, excluding 'SR'
                and 'dur'.
                The arg_value may either be a number or a string. Using a
                string will defer the evaluation, i.e. making the argument
                a symbolic parameter.
            duration: The duration of the segment (s)
        """

        validate_function_and_args_dict(function, args_dict)

        self.name = name
        self.function = function
        self.args_dict = args_dict
        self.duration = duration

        symbols = {v: k for (k, v) in args_dict.items() if isinstance(v, str)}
        self._symbols = symbols

    @property
    def symbols(self):
        return self._symbols

    def forge(self, SR: int, **kwargs) -> np.ndarray:
        """
        Forge the segment into an array. Keyword arguments can
        contain a duration (must be called dur) and should otherwise
        specify values for any symbols in the segment

        Args:
            SR: The sample rate (Sa/s)
        """

        duration = None

        if 'dur' in kwargs.keys():
            duration = kwargs.pop('dur')
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
        args_dict.update({'SR': SR, 'dur': duration})
        args_dict.update({self._symbols[s]: kwargs[s] for s in kwargs.keys()})

        array = self.function(**args_dict)

        return array

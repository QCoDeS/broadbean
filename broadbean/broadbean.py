import functools as ft
import logging
import warnings
from copy import deepcopy
from inspect import signature
from typing import Callable, Dict, List, Tuple, Union

import numpy as np

log = logging.getLogger(__name__)


class PulseAtoms:
    """
    A class full of static methods.
    The basic pulse shapes.

    Any pulse shape function should return a list or an np.array
    and have SR, npoints as its final two arguments.

    Rounding errors are a real concern/pain in the business of
    making waveforms of short duration (few samples). Therefore,
    the PulseAtoms take the number of points rather than the
    duration as input argument, so that all ambiguity can be handled
    in one place (the _subelementBuilder)
    """

    @staticmethod
    def sine(
        freq: float, ampl: float, off: float, phase: float, SR: float, npts
    ) -> np.array:
        time = np.linspace(0, npts / SR, int(npts), endpoint=False)
        freq *= 2 * np.pi
        return ampl * np.sin(freq * time + phase) + off

    @staticmethod
    def ramp(start: float, stop: float, SR: float, npts: int) -> Tuple[np.array]:
        dur = npts/SR
        slope = (stop-start)/dur
        time = np.linspace(0, dur, int(npts), endpoint=False)
        return (slope*time+start)

    @staticmethod
    def waituntil(dummy: float, SR: float, npts: int) -> np.array:
        # for internal call signature consistency, a dummy variable is needed
        return np.zeros(int(npts))

    @staticmethod
    def gaussian(
        ampl: float, sigma: float, mu: float, offset: float, SR: float, npts: int
    ) -> np.array:
        """
        Returns a Gaussian of peak height ampl (when offset==0)

        Is by default centred in the middle of the interval
        """
        dur = npts/SR
        time = np.linspace(0, dur, int(npts), endpoint=False)
        centre = dur / 2
        baregauss = np.exp(-((time - mu - centre) ** 2) / (2 * sigma**2))
        return ampl * baregauss + offset

    @staticmethod
    def gaussian_smooth_cutoff(
        ampl: float, sigma: float, mu: float, offset: float, SR: float, npts: int
    ) -> np.array:
        """
        Returns a Gaussian of peak height ampl (when offset==0)

        Is by default centred in the middle of the interval

        smooth cutoff by making offsetting the Gaussian so endpoint = 0 and normalizing the hight to 1
        """
        dur = npts/SR
        time = np.linspace(0, dur, int(npts), endpoint=False)
        centre = dur / 2
        baregauss = np.exp(-((time - mu - centre) ** 2) / (2 * sigma**2)) - np.exp(
            -((0 - mu - centre) ** 2) / (2 * sigma**2)
        )
        normalization = 1 / (1.0 - np.exp(-((0 - mu - centre) ** 2) / (2 * sigma**2)))
        return ampl * baregauss / normalization + offset


def marked_for_deletion(replaced_by: Union[str, None]=None) -> Callable:
    """
    A decorator for functions we want to kill. The function still
    gets called.
    """
    def decorator(func):
        @ft.wraps(func)
        def warner(*args, **kwargs):
            warnstr = f'{func.__name__} is obsolete.'
            if replaced_by:
                warnstr += f' Please use {replaced_by} insted.'
            warnings.warn(warnstr)
            return func(*args, **kwargs)
        return warner
    return decorator


def _channelListSorter(channels: List[Union[str, int]]) -> List[Union[str, int]]:
    """
    Sort a list of channel names. Channel names can be ints or strings. Sorts
    ints as being before strings.
    """
    intlist: List[Union[str, int]] = []
    intlist = [ch for ch in channels if isinstance(ch, int)]
    strlist: List[Union[str, int]] = []
    strlist = [ch for ch in channels if isinstance(ch, str)]

    sorted_list = sorted(intlist) + sorted(strlist)

    return sorted_list

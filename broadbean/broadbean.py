import logging
import warnings
from typing import List, Dict, Union, Callable
from inspect import signature
from copy import deepcopy
import functools as ft

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
    def sine(freq, ampl, off, phase, SR, npts):
        time = np.linspace(0, npts/SR, int(npts), endpoint=False)
        freq *= 2*np.pi
        return (ampl*np.sin(freq*time+phase)+off)

    @staticmethod
    def ramp(start, stop, SR, npts):
        dur = npts/SR
        slope = (stop-start)/dur
        time = np.linspace(0, dur, int(npts), endpoint=False)
        return (slope*time+start)

    @staticmethod
    def waituntil(dummy, SR, npts):
        # for internal call signature consistency, a dummy variable is needed
        return np.zeros(int(npts))

    @staticmethod
    def gaussian(ampl, sigma, mu, offset, SR, npts):
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
    def gaussian_smooth_cutoff(ampl, sigma, mu, offset, SR, npts):
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


class _AWGOutput:
    """
    Class used inside Sequence.outputForAWGFile

    Allows for easy-access slicing to return several valid tuples
    for the QCoDeS Tektronix AWG 5014 driver from the same sequence.

    Example:
    A sequence, myseq, specifies channels 1, 2, 3, 4.

    out = myseq.outputForAWGFile()

    out[:] <--- tuple with all channels
    out[1:3] <--- tuple with channels 1, 2
    out[2] <--- tuple with channel 2
    """

    def __init__(self, rawpackage, channels):
        """
        Rawpackage is a tuple:
        (wfms, m1s, m2s, nreps, trig_wait, goto, jump)

        Channels is a list of what the channels were called in their
        sequence object whence this instance is created
        """

        self.channels = channels

        self._channels = {}
        for ii in range(len(rawpackage[0])):
            self._channels[ii] = {'wfms': rawpackage[0][ii],
                                  'm1s': rawpackage[1][ii],
                                  'm2s': rawpackage[2][ii]}
        self.nreps = rawpackage[3]
        self.trig_wait = rawpackage[4]
        self.goto = rawpackage[5]
        self.jump = rawpackage[6]

    def __getitem__(self, key):

        if isinstance(key, int):
            if key in self._channels.keys():
                output = ([self._channels[key]['wfms']],
                          [self._channels[key]['m1s']],
                          [self._channels[key]['m2s']],
                          self.nreps, self.trig_wait, self.goto, self.jump)

                return output
            else:
                raise KeyError(f"{key} is not a valid key.")

        if isinstance(key, slice):
            start = key.start
            if start is None:
                start = 0

            stop = key.stop
            if stop is None:
                stop = len(self._channels.keys())

            step = key.step
            if step is None:
                step = 1

            indeces = range(start, stop, step)

            wfms = [self._channels[ind]['wfms'] for ind in indeces]
            m1s = [self._channels[ind]['m1s'] for ind in indeces]
            m2s = [self._channels[ind]['m2s'] for ind in indeces]

            output = (wfms, m1s, m2s,
                      self.nreps, self.trig_wait, self.goto, self.jump)

            return output

        raise KeyError('Key must be int or slice!')

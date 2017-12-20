import logging
import math
import warnings
from typing import Tuple, List, Dict, cast
from inspect import signature
from copy import deepcopy
import functools as ft
import numpy as np
import matplotlib.pyplot as plt

from broadbean.ripasso import applyInverseRCFilter

plt.ion()

log = logging.getLogger(__name__)


class SequencingError(Exception):
    pass


class SegmentDurationError(Exception):
    pass


class ElementDurationError(Exception):
    pass


class SequenceConsistencyError(Exception):
    pass


class SequenceCompatibilityError(Exception):
    pass


class SpecificationInconsistencyError(Exception):
    pass


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
    def sine(freq, ampl, off, SR, npts):
        time = np.linspace(0, npts/SR, npts)
        freq *= 2*np.pi
        return (ampl*np.sin(freq*time)+off)

    @staticmethod
    def ramp(start, stop, SR, npts):
        dur = npts/SR
        slope = (stop-start)/dur
        time = np.linspace(0, dur, npts)
        return (slope*time+start)

    @staticmethod
    def waituntil(dummy, SR, npts):
        # for internal call signature consistency, a dummy variable is needed
        return np.zeros(npts)

    @staticmethod
    def gaussian(ampl, sigma, mu, offset, SR, npts):
        """
        Returns a Gaussian of integral ampl (when offset==0)

        Is by default centred in the middle of the interval
        """
        dur = npts/SR
        time = np.linspace(0, dur, npts)
        centre = dur/2
        baregauss = np.exp((-(time-mu-centre)**2/(2*sigma**2)))
        normalisation = 1/np.sqrt(2*sigma**2*np.pi)
        return ampl*baregauss*normalisation+offset


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
                raise KeyError('{} is not a valid key.'.format(key))

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


class BluePrint():
    """
    The class to contain the bluePrint of an element.

    Several bluePrints may be passed to the elementBuilder, which turns
    them into numpy arrays.
    """

    def __init__(self, funlist=None, argslist=None, namelist=None,
                 marker1=None, marker2=None, segmentmarker1=None,
                 segmentmarker2=None, SR=None, durslist=None):
        """
        Create a BluePrint instance

        Args:
            funlist (list): List of functions
            argslist (list): List of tuples of arguments
            namelist (list): List of names for the functions
            marker1 (list): List of marker1 specification tuples
            marker2 (list): List of marker2 specifiation tuples
            durslist (list): List of durations

        Returns:
            BluePrint
        """
        # TODO: validate input

        # Sanitising
        if funlist is None:
            funlist = []
        if argslist is None:
            argslist = []
        if namelist is None:
            namelist = []
        if durslist is None:
            durslist = []

        # Are the lists of matching lengths?
        lenlist = [len(funlist), len(argslist), len(namelist), len(durslist)]

        if len(set(lenlist)) is not 1:
            raise ValueError('All input lists must be of same length. '
                             'Received lengths: {}'.format(lenlist))
        # Are the names valid names?
        for name in namelist:
            if not isinstance(name, str):
                raise ValueError('All segment names must be strings. '
                                 'Received {}'.format(name))
            elif name is not '':
                if name[-1].isdigit():
                    raise ValueError('Segment names are not allowed to end'
                                     ' in a number. {} is '.format(name) +
                                     'therefore not a valid name.')

        self._funlist = funlist

        # Make special functions live in the funlist but transfer their names
        # to the namelist
        # Infer names from signature if not given, i.e. allow for '' names
        for ii, name in enumerate(namelist):
            if isinstance(funlist[ii], str):
                namelist[ii] = funlist[ii]
            elif name == '':
                namelist[ii] = funlist[ii].__name__

        # Allow single arguments to be given as not tuples
        for ii, args in enumerate(argslist):
            if not isinstance(args, tuple):
                argslist[ii] = (args,)
        self._argslist = argslist

        self._namelist = namelist
        namelist = self._make_names_unique(namelist)

        # initialise markers
        if marker1 is None:
            self.marker1 = []
        else:
            self.marker1 = marker1
        if marker2 is None:
            self.marker2 = []
        else:
            self.marker2 = marker2
        if segmentmarker1 is None:
            self._segmark1 = [(0, 0)]*len(funlist)
        else:
            self._segmark1 = segmentmarker1
        if segmentmarker2 is None:
            self._segmark2 = [(0, 0)]*len(funlist)
        else:
            self._segmark2 = segmentmarker2

        if durslist is not None:
            self._durslist = list(durslist)
        else:
            self._durslist = None

        self._SR = SR

    @staticmethod
    def _basename(string):
        """
        Remove trailing numbers from a string.
        """

        if not isinstance(string, str):
            raise ValueError('_basename received a non-string input!'
                             ' Got the following: {}'.format(string))

        if string == '':
            return string
        if not(string[-1].isdigit()):
            return string
        else:
            counter = 0
            for ss in string[::-1]:
                if ss.isdigit():
                    counter += 1
                else:
                    break
            return string[:-counter]

        # lst = [letter for letter in string if not letter.isdigit()]
        # return ''.join(lst)

    @staticmethod
    def _make_names_unique(lst):
        """
        Make all strings in the input list unique
        by appending numbers to reoccuring strings

        Args:
            lst (list): List of strings. Intended for the _namelist

        """

        if not isinstance(lst, list):
            raise ValueError('_make_names_unique received a non-list input!'
                             ' Got {}'.format(lst))

        baselst = [BluePrint._basename(lstel) for lstel in lst]
        uns = np.unique(baselst)

        for un in uns:
            inds = [ii for ii, el in enumerate(baselst) if el == un]
            for ii, ind in enumerate(inds):
                # Do not append numbers to the first occurence
                if ii == 0:
                    lst[ind] = '{}'.format(un)
                else:
                    lst[ind] = '{}{}'.format(un, ii+1)

        return lst

    @property
    def length_segments(self):
        """
        Returns the number of segments in the blueprint
        """
        return len(self._namelist)

    @property
    def duration(self):
        """
        The total duration of the BluePrint. If necessary, all the arrays
        are built.
        """
        waits = 'waituntil' in self._funlist
        ensavgs = 'ensureaverage_fixed_level' in self._funlist

        if (not(waits) and not(ensavgs)):
            return sum(self._durslist)
        elif (waits and not(ensavgs)):
            waitdurations = self._makeWaitDurations()
            return sum(waitdurations)
        elif ensavgs:
            # TODO: call the forger
            raise NotImplementedError('ensureaverage_fixed_level does not'
                                      ' exist yet. Cannot proceed')

    @property
    def points(self):
        """
        The total number of points in the BluePrint. If necessary,
        all the arrays are built.
        """
        waits = 'waituntil' in self._funlist
        ensavgs = 'ensureaverage_fixed_level' in self._funlist
        SR = self.SR

        if SR is None:
            raise ValueError('No sample rate specified, can not '
                             'return the number of points.')

        if (not(waits) and not(ensavgs)):
            return int(np.round(sum(self._durslist)*SR))
        elif (waits and not(ensavgs)):
            waitdurations = self._makeWaitDurations()
            return int(np.round(sum(waitdurations)*SR))
        elif ensavgs:
            # TODO: call the forger
            raise NotImplementedError('ensureaverage_fixed_level does not'
                                      ' exist yet. Cannot proceed')

    @property
    def durations(self):
        """
        The list of durations
        """
        return self._durslist

    @property
    def SR(self):
        """
        Sample rate of the blueprint
        """
        return self._SR

    @property
    def description(self):
        """
        Returns a dict describing the blueprint.
        """
        desc = {}  # the dict to return

        no_segs = len(self._namelist)

        for sn in range(no_segs):
            segkey = 'segment_{:02d}'.format(sn+1)
            desc[segkey] = {}
            desc[segkey]['name'] = self._namelist[sn]
            if self._funlist[sn] == 'waituntil':
                desc[segkey]['function'] = self._funlist[sn]
            else:
                funname = str(self._funlist[sn])[1:]
                funname = funname[:funname.find(' at')]
                desc[segkey]['function'] = funname
            desc[segkey]['durations'] = self._durslist[sn]
            if desc[segkey]['function'] == 'waituntil':
                desc[segkey]['arguments'] = {'waittime': self._argslist[sn]}
            else:
                sig = signature(self._funlist[sn])
                desc[segkey]['arguments'] = dict(zip(sig.parameters,
                                                     self._argslist[sn]))

        desc['marker1_abs'] = self.marker1
        desc['marker2_abs'] = self.marker2
        desc['marker1_rel'] = self._segmark1
        desc['marker2_rel'] = self._segmark2

        return desc

    def _makeWaitDurations(self):
        """
        Translate waituntills into durations and return that list.
        """

        if 'ensureaverage_fixed_level' in self._funlist:
            raise NotImplementedError('There is an "ensureaverage_fixed_level"'
                                      ' in this BluePrint. Cannot compute.')

        funlist = self._funlist.copy()
        durations = self._durslist.copy()
        argslist = self._argslist

        no_of_waits = funlist.count('waituntil')

        waitpositions = [ii for ii, el in enumerate(funlist)
                         if el == 'waituntil']

        # Calculate elapsed times

        for nw in range(no_of_waits):
            pos = waitpositions[nw]
            funlist[pos] = PulseAtoms.waituntil
            elapsed_time = sum(durations[:pos])
            wait_time = argslist[pos][0]
            dur = wait_time - elapsed_time
            if dur < 0:
                raise ValueError('Inconsistent timing. Can not wait until ' +
                                 '{} at position {}.'.format(wait_time, pos) +
                                 ' {} elapsed already'.format(elapsed_time))
            else:
                durations[pos] = dur

        return durations

    def showPrint(self):
        """
        Pretty-print the contents of the BluePrint. Not finished.
        """
        # TODO: tidy up this method and make it use the description property

        if self._durslist is None:
            dl = [None]*len(self._namelist)
        else:
            dl = self._durslist

        datalists = [self._namelist, self._funlist, self._argslist,
                     dl]

        lzip = zip(*datalists)

        print('Legend: Name, function, arguments, timesteps, durations')

        for ind, (name, fun, args, dur) in enumerate(lzip):
            ind_p = ind+1
            if fun == 'waituntil':
                fun_p = fun
            else:
                fun_p = fun.__str__().split(' ')[1]

            list_p = [ind_p, name, fun_p, args, dur]
            print('Segment {}: "{}", {}, {}, {}'.format(*list_p))
        print('-'*10)

    def changeArg(self, name, arg, value, replaceeverywhere=False):
        """
        Change an argument of one or more of the functions in the blueprint.

        Args:
            name (str): The name of the segment in which to change an argument
            arg (Union[int, str]): Either the position (int) or name (str) of
                the argument to change
            value (Union[int, float]): The new value of the argument
            replaceeverywhere (bool): If True, the same argument is overwritten
                in ALL segments where the name matches. E.g. 'gaussian1' will
                match 'gaussian', 'gaussian2', etc. If False, only the segment
                with exact name match gets a replacement.

        Raises:
            ValueError: If the argument can not be matched (either the argument
                name does not match or the argument number is wrong).
            ValueError: If the name can not be matched.

        """
        # TODO: is there any reason to use tuples internally?

        if replaceeverywhere:
            basename = BluePrint._basename
            name = basename(name)
            nmlst = self._namelist
            replacelist = [nm for nm in nmlst if basename(nm) == name]
        else:
            replacelist = [name]

        # Validation
        if name not in self._namelist:
            raise ValueError('No segment of that name in blueprint.'
                             ' Contains segments: {}'.format(self._namelist))

        for name in replacelist:

            position = self._namelist.index(name)
            function = self._funlist[position]
            sig = signature(function)

            # Validation
            if isinstance(arg, str):
                if arg not in sig.parameters:
                    raise ValueError('No such argument of function '
                                     '{}.'.format(function.__name__) +
                                     'Has arguments '
                                     '{}.'.format(sig.parameters.keys()))
            # Each function has two 'secret' arguments, SR and dur
            user_params = len(sig.parameters)-2
            if isinstance(arg, int) and (arg not in range(user_params)):
                raise ValueError('No argument {} '.format(arg) +
                                 'of function {}.'.format(function.__name__) +
                                 ' Has {} '.format(user_params) +
                                 'arguments.')

            # allow the user to input single values instead of (val,)
            no_of_args = len(self._argslist[position])
            if not isinstance(value, tuple) and no_of_args == 1:
                value = (value,)

            if isinstance(arg, str):
                for ii, param in enumerate(sig.parameters):
                    if arg == param:
                        arg = ii
                        break

            # Mutating the immutable...
            larg = list(self._argslist[position])
            larg[arg] = value
            self._argslist[position] = tuple(larg)

    def changeDuration(self, name, dur, replaceeverywhere=False):
        """
        Change the duration of one or more segments in the blueprint

        Args:
            name (str): The name of the segment in which to change duration
            dur (Union[float, int]): The new duration.
            replaceeverywhere (Optional[bool]): If True, the duration(s)
                is(are) overwritten in ALL segments where the name matches.
                E.g. 'gaussian1' will match 'gaussian', 'gaussian2',
                etc. If False, only the segment with exact name match
                gets a replacement.

        Raises:
            ValueError: If durations are not specified for the blueprint
            ValueError: If too many or too few durations are given.
            ValueError: If no segment matches the name.
            ValueError: If dur is not positive
            ValueError: If SR is given for the blueprint and dur is less than
                1/SR.
        """

        if (not(isinstance(dur, float)) and not(isinstance(dur, int))):
            raise ValueError('New duration must be an int or a float. '
                             'Received {}'.format(type(dur)))

        if replaceeverywhere:
            basename = BluePrint._basename
            name = basename(name)
            nmlst = self._namelist
            replacelist = [nm for nm in nmlst if basename(nm) == name]
        else:
            replacelist = [name]

        # Validation
        if name not in self._namelist:
            raise ValueError('No segment of that name in blueprint.'
                             ' Contains segments: {}'.format(self._namelist))

        for name in replacelist:
            position = self._namelist.index(name)

            if dur <= 0:
                raise ValueError('Duration must be strictly greater '
                                 'than zero.')

            if self.SR is not None:
                if dur*self.SR < 1:
                    raise ValueError('Duration too short! Must be at'
                                     ' least 1/sample rate.')

            self._durslist[position] = dur

    def setSR(self, SR):
        """
        Set the associated sample rate

        Args:
            SR (Union[int, float]): The sample rate in Sa/s.
        """
        self._SR = SR

    def setSegmentMarker(self, name, specs, markerID):
        """
        Bind a marker to a specific segment.

        Args:
            name (str): Name of the segment
            specs (tuple): Marker specification tuple, (delay, duration),
                where the delay is relative to the segment start
            markerID (int): Which marker channel to output on. Must be 1 or 2.
        """
        if markerID not in [1, 2]:
            raise ValueError('MarkerID must be either 1 or 2.'
                             ' Received {}.'.format(markerID))

        markerselect = {1: self._segmark1, 2: self._segmark2}
        position = self._namelist.index(name)

        # TODO: Do we need more than one bound marker per segment?
        markerselect[markerID][position] = specs

    def removeSegmentMarker(self, name: str, markerID: int) -> None:
        """
        Remove all bound markers from a specific segment

        Args:
            name (str): Name of the segment
            markerID (int): Which marker channel to remove from (1 or 2).
            number (int): The number of the marker, in case several markers are
                bound to one element. Default: 1 (the first marker).
        """
        if markerID not in [1, 2]:
            raise ValueError('MarkerID must be either 1 or 2.'
                             ' Received {}.'.format(markerID))

        markerselect = {1: self._segmark1, 2: self._segmark2}
        try:
            position = self._namelist.index(name)
        except ValueError:
            raise KeyError('No segment named {} in this BluePrint.'
                           ''.format(name))
        markerselect[markerID][position] = (0, 0)

    def copy(self):
        """
        Returns a copy of the BluePrint
        """

        # Needed because of input validation in __init__
        namelist = [self._basename(name) for name in self._namelist.copy()]

        return BluePrint(self._funlist.copy(),
                         self._argslist.copy(),
                         namelist,
                         self.marker1.copy(),
                         self.marker2.copy(),
                         self._segmark1.copy(),
                         self._segmark2.copy(),
                         self._SR,
                         self._durslist)

    def insertSegment(self, pos, func, args=(), dur=None, name=None,
                      durs=None):
        """
        Insert a segment into the bluePrint.

        Args:
            pos (int): The position at which to add the segment. Counts like
                a python list; 0 is first, -1 is last. Values below -1 are
                not allowed, though.
            func (function): Function describing the segment. Must have its
               duration as the last argument (unless its a special function).
            args (Optional[Tuple[Any]]): Tuple of arguments BESIDES duration.
                Default: ()
            dur (Optional[Union[int, float]]): The duration of the
                segment. Must be given UNLESS the segment is
                'waituntil' or 'ensureaverage_fixed_level'
            name Optional[str]: Name of the segment. If none is given,
                the segment will receive the name of its function,
                possibly with a number appended.

        Raises:
            ValueError: If the position is negative
            ValueError: If the name ends in a number
        """

        # Validation
        has_ensureavg = ('ensureaverage_fixed_level' in self._funlist or
                         'ensureaverage_fixed_dur' in self._funlist)
        if func == 'ensureaverage_fixed_level' and has_ensureavg:
            raise ValueError('Can not have more than one "ensureaverage"'
                             ' segment in a blueprint.')

        if durs is not None:
            warnings.warn('Deprecation warning: please specify "dur" rather '
                          'than "durs" when inserting a segment')
            if dur is None:
                dur = durs
            else:
                raise ValueError('You can not specify "durs" AND "dur"!')
        # Take care of 'waituntil'

        # allow users to input single values
        if not isinstance(args, tuple):
            args = (args,)

        if pos < -1:
            raise ValueError('Position must be strictly larger than -1')

        if name is None or name == '':
            if func == 'waituntil':
                name = 'waituntil'
            else:
                name = func.__name__
        elif isinstance(name, str):
            if len(name) > 0:
                if name[-1].isdigit():
                    raise ValueError('Segment name must not end in a number')

        if pos == -1:
            self._namelist.append(name)
            self._namelist = self._make_names_unique(self._namelist)
            self._funlist.append(func)
            self._argslist.append(args)
            self._segmark1.append((0, 0))
            self._segmark2.append((0, 0))
            self._durslist.append(dur)
        else:
            self._namelist.insert(pos, name)
            self._namelist = self._make_names_unique(self._namelist)
            self._funlist.insert(pos, func)
            self._argslist.insert(pos, args)
            self._segmark1.insert(pos, (0, 0))
            self._segmark2.insert(pos, (0, 0))
            self._durslist.insert(pos, dur)

    def removeSegment(self, name):
        """
        Remove the specified segment from the blueprint.

        Args:
            name (str): The name of the segment to remove.
        """
        try:
            position = self._namelist.index(name)
        except ValueError:
            raise KeyError('No segment called {} in blueprint.'.format(name))

        del self._funlist[position]
        del self._argslist[position]
        del self._namelist[position]
        del self._segmark1[position]
        del self._segmark2[position]
        del self._durslist[position]

        self._namelist = self._make_names_unique(self._namelist)

    def plot(self, SR=None):
        """
        Plot the blueprint.

        Args:
            SR (Optional[Union[int, None]]): The sample rate. If None,
                the sample rate of the blueprint is used.

        Raises:
            ValueError: If no sample rate is provided as argument nor set for
            the blueprint.
        """

        if self.SR is None and SR is None:
            raise ValueError('No sample rate specified. Please provide one!')

        if SR is None:
            SR = self.SR

        bluePrintPlotter(self)

    def __add__(self, other):
        """
        Add two BluePrints. The second argument is appended to the first
        and a new BluePrint is returned.

        Args:
            other (BluePrint): A BluePrint instance

        Returns:
            BluePrint: A new blueprint.

        Raises:
            ValueError: If the input is not a BluePrint instance
        """
        if not isinstance(other, BluePrint):
            raise ValueError("""
                             BluePrint can only be added to another Blueprint.
                             Received an object of type {}
                             """.format(type(other)))

        nl = [self._basename(name) for name in self._namelist]
        nl += [self._basename(name) for name in other._namelist]
        al = self._argslist + other._argslist
        fl = self._funlist + other._funlist
        m1 = self.marker1 + other.marker1
        m2 = self.marker2 + other.marker2
        sm1 = self._segmark1 + other._segmark1
        sm2 = self._segmark2 + other._segmark2
        dl = self._durslist + other._durslist

        new_bp = BluePrint()

        new_bp._namelist = new_bp._make_names_unique(nl.copy())
        new_bp._funlist = fl.copy()
        new_bp._argslist = al.copy()
        new_bp.marker1 = m1.copy()
        new_bp.marker2 = m2.copy()
        new_bp._segmark1 = sm1.copy()
        new_bp._segmark2 = sm2.copy()
        new_bp._durslist = dl.copy()

        if self.SR is not None:
            new_bp.setSR(self.SR)

        return new_bp

    def __eq__(self, other):
        """
        Compare two blueprints. They are the same iff all
        lists are identical.

        Args:
            other (BluePrint): A BluePrint instance

        Returns:
            bool: whether the two blueprints are identical

        Raises:
            ValueError: If the input is not a BluePrint instance
        """
        if not isinstance(other, BluePrint):
            raise ValueError("""
                             Blueprint can only be compared to another
                             Blueprint.
                             Received an object of type {}
                             """.format(type(other)))

        if not self._namelist == other._namelist:
            return False
        if not self._funlist == other._funlist:
            return False
        if not self._argslist == other._argslist:
            return False
        if not self.marker1 == other.marker1:
            return False
        if not self.marker2 == other.marker2:
            return False
        if not self._segmark1 == other._segmark1:
            return False
        if not self._segmark2 == other._segmark2:
            return False
        return True


class Element:
    """
    Object representing an element. An element is a collection of waves that
    are to be run simultaneously. The element consists of a number of channels
    that are then each filled with anything of the appropriate length.
    """

    def __init__(self):

        # The internal data structure, a dict with key channel number
        # Each value is a dict with the following possible keys, values:
        # 'blueprint': a BluePrint
        # 'channelname': channel name for later use with a Tektronix AWG5014
        # 'array': an np.array
        # 'SR': Sample rate. Used with array.
        #
        # Another dict is meta, which holds:
        # 'duration': duration in seconds of the entire element.
        # 'SR': sample rate of the element
        # These two values are added/updated upon validation of the durations

        self._data = {}
        self._meta = {}

    def addBluePrint(self, channel, blueprint):
        """
        Add a blueprint to the element on the specified channel.
        Overwrites whatever was there before.
        """
        if not isinstance(blueprint, BluePrint):
            raise ValueError('Invalid blueprint given. Must be an instance'
                             ' of the BluePrint class.')

        if [] in [blueprint._funlist, blueprint._argslist, blueprint._namelist,
                  blueprint._durslist]:
            raise ValueError('Received empty BluePrint. Can not proceed.')

        # important: make a copy of the blueprint
        newprint = blueprint.copy()

        self._data[channel] = {}
        self._data[channel]['blueprint'] = newprint

    def addArray(self, channel, array, SR, m1=None, m2=None):
        """
        Add an array of voltage value to the element on the specified channel.
        Overwrites whatever was there before.

        Args:
            channel (int): The channel number
            array (numpy.ndarray): The array of values
            SR (int): The sample rate in Sa/s
        """

        # TODO: this is very Tektronix AWG-centric, that a channel has a
        # waveform and two markers. Think about generalising.

        time = np.linspace(0, len(array)/SR, len(array))
        if m1 is None:
            m1 = np.zeros_like(time)
        elif len(m1) != len(array):
            raise ValueError('Lengths of array and m1 do not match!')

        if m2 is None:
            m2 = np.zeros_like(time)
        elif len(m2) != len(array):
            raise ValueError('Lengths of array and m2 do not match!')

        self._data[channel] = {}
        self._data[channel]['array'] = [array, m1, m2, time]
        self._data[channel]['SR'] = SR

    def validateDurations(self):
        """
        Check that all channels have the same specified duration, number of
        points and sample rate.
        """

        # pick out the channel entries
        channels = self._data.values()

        # First the sample rate
        SRs = []
        for channel in channels:
            if 'blueprint' in channel.keys():
                SRs.append(channel['blueprint'].SR)
            elif 'array' in channel.keys():
                SR = channel['SR']
                SRs.append(SR)

        if not SRs.count(SRs[0]) == len(SRs):
            errmssglst = zip(list(self._data.keys()), SRs)
            raise ElementDurationError('Different channels have different '
                                       'SRs. (Channel, SR): '
                                       '{}'.format(list(errmssglst)))

        # Next the total time
        durations = []
        for channel in channels:
            if 'blueprint' in channel.keys():
                durations.append(channel['blueprint'].duration)
            elif 'array' in channel.keys():
                length = len(channel['array'][0])/channel['SR']
                durations.append(length)

        if None not in SRs:
            atol = min(SRs)
        else:
            atol = 1e-9

        if not np.allclose(durations, durations[0], atol=atol):
            errmssglst = zip(list(self._data.keys()), durations)
            raise ElementDurationError('Different channels have different '
                                       'durations. (Channel, duration): '
                                       '{}s'.format(list(errmssglst)))

        # Finally the number of points
        # (kind of redundant if sample rate and duration match?)
        npts = []
        for channel in channels:
            if 'blueprint' in channel.keys():
                npts.append(channel['blueprint'].points)
            elif 'array' in channel.keys():
                length = len(channel['array'][0])
                npts.append(length)

        if not npts.count(npts[0]) == len(npts):
            errmssglst = zip(list(self._data.keys()), npts)
            raise ElementDurationError('Different channels have different '
                                       'npts. (Channel, npts): '
                                       '{}'.format(list(errmssglst)))

        # If these three tests pass, we equip the dictionary with convenient
        # info used by Sequence
        self._meta['SR'] = SRs[0]
        self._meta['duration'] = durations[0]

    def getArrays(self):
        """
        Return arrays of the element. Heavily used by the Sequence.

        Returns:
            dict:
              Dictionary with channel numbers (ints) as keys and forged
              blueprints as values. A forged blueprint is a numpy
              array given by np.array([wfm, m1, m2, time]).

        """

        outdict = {}
        for channel, signal in self._data.items():
            if 'array' in signal.keys():
                outdict[channel] = signal['array']
            elif 'blueprint' in signal.keys():
                bp = signal['blueprint']
                durs = bp.durations
                SR = bp.SR
                outdict[channel] = (list(_subelementBuilder(bp, SR, durs)[0]) +
                                    [_subelementBuilder(bp, SR, durs)[1]])

        return outdict

    @property
    def SR(self):
        """
        Returns the sample rate, if well-defined. Else raises
        an error about what went wrong.
        """
        # Will either raise an error or set self._data['SR']
        self.validateDurations()

        return self._meta['SR']

    @property
    def points(self) -> int:
        """
        Returns the number of points of each channel if that number is
        well-defined. Else an error is raised.
        """
        self.validateDurations()

        # pick out what is on the channels
        channels = self._data.values()

        # if validateDurations did not raise an error, all channels
        # have the same number of points
        for channel in channels:
            if 'blueprint' in channel.keys():
                return channel['blueprint'].points
            elif 'array' in channel.keys():
                return len(channel['array'][0])

    @property
    def duration(self):
        """
        Returns the duration in seconds of the element, if said duration is
        well-defined. Else raises an error.
        """
        # Will either raise an error or set self._data['SR']
        self.validateDurations()

        return self._meta['duration']

    @property
    def channels(self):
        """
        The channels that has something on them
        """
        chans = [key for key in self._data.keys()]
        return chans

    @property
    def description(self):
        """
        Returns a dict describing the element.
        """
        desc = {}

        for key, val in self._data.items():
            if 'blueprint' in val.keys():
                desc[str(key)] = val['blueprint'].description
            elif 'array' in val.keys():
                desc[str(key)] = 'array'

        return desc

    def changeArg(self, channel, name, arg, value, replaceeverywhere=False):
        """
        Change the argument of a function of the blueprint on the specified
        channel.

        Args:
            channel (int): The channel where the blueprint sits.
            name (str): The name of the segment in which to change an argument
            arg (Union[int, str]): Either the position (int) or name (str) of
                the argument to change
            value (Union[int, float]): The new value of the argument
            replaceeverywhere (bool): If True, the same argument is overwritten
                in ALL segments where the name matches. E.g. 'gaussian1' will
                match 'gaussian', 'gaussian2', etc. If False, only the segment
                with exact name match gets a replacement.

        Raises:
            ValueError: If the specified channel has no blueprint.
            ValueError: If the argument can not be matched (either the argument
                name does not match or the argument number is wrong).
        """
        # avoid a KeyError in the next if statement
        if channel not in self.channels:
            self._data[channel] = {'': ''}

        if 'blueprint' not in self._data[channel].keys():
            raise ValueError('No blueprint on channel {}.'.format(channel))

        bp = self._data[channel]['blueprint']

        bp.changeArg(name, arg, value, replaceeverywhere)

    def changeDuration(self, channel, name, newdur, replaceeverywhere=False):
        """
        Change the duration(s) of a segment of the blueprint on the specified
        channel

        Args:
            channel (int): The channel holding the blueprint in question
            name (str): The name of the segment to modify
            newdur (Union[tuple, int, float]): The new duration(s). Must be a
                tuple if more than one is provided.
            replaceeverywhere (Optional[bool]): If True, all segments
                matching the base
                name given will have their duration changed. If False, only the
                segment with an exact name match will have its duration
                changed. Default: False.
        """

        # avoid a KeyError in the next if statement
        if channel not in self.channels:
            self._data[channel] = {'': ''}

        if 'blueprint' not in self._data[channel].keys():
            raise ValueError('No blueprint on channel {}.'.format(channel))

        bp = self._data[channel]['blueprint']

        bp.changeDuration(name, newdur, replaceeverywhere)

    def copy(self):
        """
        Return a copy of the element
        """
        new = Element()
        new._data = deepcopy(self._data)
        new._meta = deepcopy(self._meta)
        return new

    def plotElement(self):
        """
        Plot the element. Currently only works if ONLY BluePrints are added.
        """

        # First check that the element is valid
        self.validateDurations()

        blueprints = [val['blueprint'] for val in self._data.values()]

        bluePrintPlotter(blueprints)

        # hack the ylabels
        cur_fig = plt.gcf()
        for ii, channel in enumerate(self.channels):
            oldlabel = cur_fig.axes[ii].get_ylabel()
            newlabel = oldlabel.replace('Signal', 'Ch {}'.format(channel))
            cur_fig.axes[ii].set_ylabel(newlabel)

    def __eq__(self, other):
        if not isinstance(other, Element):
            return False
        elif not self._data == other._data:
            return False
        elif not self._meta == other._meta:
            return False
        else:
            return True


class Sequence:
    """
    Sequence object
    """

    def __init__(self):
        """
        Not much to see here...
        """

        # the internal data structure, a dict with tuples as keys and values
        # the key is sequence position (int), the value is element (Element)
        self._data = {}

        # Here goes the sequencing info. Key: position
        # value: dict with keys 'twait', 'nrep', 'jump_input',
        # 'jump_target', 'goto'
        #
        # the sequencing is filled out automatically with default values
        # when an element is added
        # Note that not all output backends use all items in the list
        self._sequencing = {}

        # The dictionary to store AWG settings
        # Keys will include:
        # 'SR', 'channelX_amplitude', 'channelX_offset', 'channelX_filter'
        self._awgspecs = {}

        # The metainfo to be extracted by measurements
        # todo: I'm pretty sure this is obsolete now that description exists
        self._meta = {}

        # some backends (seqx files) allow for a sequence to have a name
        # we make the name a property of the sequence
        self._name = ''

    def __eq__(self, other):
        if not isinstance(other, Sequence):
            return False
        elif not self._data == other._data:
            return False
        elif not self._meta == other._meta:
            return False
        elif not self._awgspecs == other._awgspecs:
            return False
        elif not self._sequencing == other._sequencing:
            return False
        else:
            return True

    def __add__(self, other):
        """
        Add two sequences.
        Return a new sequence with is the right argument appended to the
        left argument.
        """

        # Validation
        if not self.checkConsistency():
            raise SequenceConsistencyError('Left hand sequence inconsistent!')
        if not other.checkConsistency():
            raise SequenceConsistencyError('Right hand sequence inconsistent!')

        if not self._awgspecs == other._awgspecs:
            raise SequenceCompatibilityError('Incompatible sequences: '
                                             'different AWG'
                                             'specifications.')

        newseq = Sequence()
        N = len(self._data)

        newdata1 = dict([(key, self.element(key).copy())
                         for key in self._data.keys()])
        newdata2 = dict([(key+N, other.element(key).copy())
                         for key in other._data.keys()])
        newdata1.update(newdata2)

        newseq._data = newdata1

        newsequencing1 = dict([(key, self._sequencing[key].copy())
                               for key in self._sequencing.keys()])
        newsequencing2 = dict()

        for key, item in other._sequencing.items():
            newitem = item.copy()
            # update goto and jump according to new sequence length
            if newitem['goto'] > 0:
                newitem['goto'] += N
            if newitem['jump_target'] > 0:
                newitem['jump_target'] += N
            newsequencing2.update({key+N: newitem})

        newsequencing1.update(newsequencing2)

        newseq._sequencing = newsequencing1

        newseq._awgspecs = other._awgspecs.copy()

        return newseq

    def copy(self):
        """
        Returns a copy of the sequence.
        """
        newseq = Sequence()
        newseq._data = deepcopy(self._data)
        newseq._meta = deepcopy(self._meta)
        newseq._awgspecs = deepcopy(self._awgspecs)
        newseq._sequencing = deepcopy(self._sequencing)

        return newseq

    def setSequenceSettings(self, pos, wait, nreps, jump, goto):
        """
        Set the sequence setting for the sequence element at pos.

        Args:
            pos (int): The sequence element (counting from 1)
            wait (int): The wait state specifying whether to wait for a
                trigger. 0: OFF, don't wait, 1: ON, wait. For some backends,
                additional integers are allowed to specify the trigger input.
                0 always means off.
            nreps (int): Number of repetitions. 0 corresponds to infinite
                repetitions
            jump (int): Event jump target, the position of a sequence element.
                If 0, the event jump state is off.
            goto (int): Goto target, the position of a sequence element.
                0 means next.
        """

        warnings.warn('Deprecation warning. This function is only compatible '
                      'with AWG5014 output and will be removed. '
                      'Please use the specific setSequencingXXX methods.')

        # Validation (some validation 'postponed' and put in checkConsistency)
        #
        # Because of different compliances for different backends,
        # most validation of these settings is deferred and performed
        # in the outputForXXX methods

        self._sequencing[pos] = {'twait': wait, 'nrep': nreps,
                                 'jump_target': jump, 'goto': goto,
                                 'jump_input': 0}

    def setSequencingTriggerWait(self, pos: int, wait: int) -> None:
        """
        Set the trigger wait for the sequence element at pos. For
        AWG 5014 out, this can be 0 or 1, For AWG 70000A output, this
        can be 0, 1, 2, or 3.

        Args:
            pos: The sequence element (counting from 1)
            wait: The wait state/input depending on backend.
        """
        self._sequencing[pos]['twait'] = wait

    def setSequencingNumberOfRepetitions(self, pos: int, nrep: int) -> None:
        """
        Set the number of repetitions for the sequence element at pos.

        Args:
            pos: The sequence element (counting from 1)
            nrep: The number of repetitions (0 means infinite)
        """
        self._sequencing[pos]['nrep'] = nrep

    def setSequencingEventInput(self, pos: int, jump_input: int) -> None:
        """
        Set the event input for the sequence element at pos. This setting is
        ignored by the AWG 5014.

        Args:
            pos: The sequence element (counting from 1)
            jump_input: The input specifier,  0 for off,
                1 for 'TrigA', 2 for 'TrigB', 3 for 'Internal'.
        """
        self._sequencing[pos]['jump_input'] = jump_input

    def setSequencingEventJumpTarget(self, pos: int, jump_target: int) -> None:
        """
        Set the event jump target for the sequence element at pos.

        Args:
            pos: The sequence element (counting from 1)
            jump_target: The sequence element to jump to (counting from 1)
        """
        self._sequencing[pos]['jump_target'] = jump_target

    def setSequencingGoto(self, pos: int, goto: int) -> None:
        """
        Set the goto target (which element to play after the current one ends)
        for the sequence element at pos.

        Args:
            pos: The sequence element (counting from 1)
            goto: The position of the element to play. 0 means 'next in line'
        """
        self._sequencing[pos]['goto'] = goto

    def setSR(self, SR):
        """
        Set the sample rate for the sequence
        """
        self._awgspecs['SR'] = SR

    def setChannelVoltageRange(self, channel, ampl, offset):
        """
        Assign the physical voltages of the channel. This is used when making
        output for .awg files. The corresponding parameters in the QCoDeS
        AWG5014 driver are called chXX_amp and chXX_offset. Please ensure that
        the channel in question is indeed in ampl/offset mode and not in
        high/low mode.

        Args:
            channel (int): The channel number
            ampl (float): The channel peak-to-peak amplitude (V)
            offset (float): The channel offset (V)
        """
        warnings.warn('Deprecation warning. This function is deprecated.'
                      ' Use setChannelAmplitude and SetChannelOffset '
                      'instead.')

        keystr = 'channel{}_amplitude'.format(channel)
        self._awgspecs[keystr] = ampl
        keystr = 'channel{}_offset'.format(channel)
        self._awgspecs[keystr] = offset

    def setChannelAmplitude(self, channel: int, ampl: float) -> None:
        """
        Assign the physical voltage amplitude of the channel. This is used
        when making output for real instruments.

        Args:
            channel: The channel number
            ampl: The channel peak-to-peak amplitude (V)
        """
        keystr = 'channel{}_amplitude'.format(channel)
        self._awgspecs[keystr] = ampl

    def setChannelOffset(self, channel: int, offset: float) -> None:
        """
        Assign the physical voltage offset of the channel. This is used
        by some backends when making output for real instruments

        Args:
            channel: The channel number
            offset: The channel offset (V)
        """
        keystr = 'channel{}_offset'.format(channel)
        self._awgspecs[keystr] = offset

    def setChannelDelay(self, channel, delay):
        """
        Assign a delay to a channel. This is used when making output for .awg
        files. Use the delay to compensate for cable length differences etc.
        Zeros are prepended to the waveforms to delay them and correspondingly
        appended to non (or less) delayed channels.

        Args:
            channel (int): The channel number
            delay (float): The required delay (s)

        Raises:
            ValueError: If a non-integer or non-non-negative channel number is
                given.
        """

        if not isinstance(channel, int) or channel < 1:
            raise ValueError('{} is not a valid '.format(channel) +
                             'channel number.')

        self._awgspecs['channel{}_delay'.format(channel)] = delay

    def setChannelFilterCompensation(self, channel, kind, order=1,
                                     f_cut=None, tau=None):
        """
        Specify a filter to compensate for.

        The specified channel will get a compensation (pre-distorion) to
        compensate for the specified frequency filter. Just to be clear:
        the INVERSE transfer function of the one you specify is applied.
        Only compensation for simple RC-circuit type high pass and low
        pass is supported.

        Args:
            channel (int): The channel to apply this to.
            kind (str): Either 'LP' or 'HP'
            order (Optional[int]): The order of the filter to compensate for.
                May be negative. Default: 1.
            f_cut (Optional[Union[float, int]]): The cut_off frequency (Hz).
            tau (Optional[Union[float, int]]): The time constant (s). Note that
                tau = 1/f_cut and that only one can be specified.

        Raises:
            ValueError: If kind is not 'LP' or 'HP'
            ValueError: If order is not an int.
            SpecificationInconsistencyError: If both f_cut and tau are given.
        """

        if kind not in ['HP', 'LP']:
            raise ValueError('Filter kind must either be "LP" (low pass) or '
                             '"HP" (high pass).')
        if not isinstance(order, int):
            raise ValueError('Filter order must be an integer.')
        if (f_cut is not None) and (tau is not None):
            raise SpecificationInconsistencyError('Can not specify BOTH a time'
                                                  ' constant and a cut-off '
                                                  'frequency.')

        keystr = 'channel{}_filtercompensation'.format(channel)
        self._awgspecs[keystr] = {'kind': kind, 'order': order, 'f_cut': f_cut,
                                  'tau': tau}

    def addElement(self, position, element):
        """
        Add an element to the sequence. Overwrites previous values.

        Args:
            position (int): The sequence position of the element (lowest: 1)
            element (Element): An element instance

        Raises:
            ValueError: If the element has inconsistent durations
        """

        # Validation
        element.validateDurations()

        # make a new copy of the element
        newelement = element.copy()

        # Data mutation
        self._data.update({position: newelement})

        # insert default sequencing settings
        self._sequencing[position] = {'twait': 0, 'nrep': 1,
                                      'jump_input': 0, 'jump_target': 0,
                                      'goto': 0}

    def checkConsistency(self, verbose=False):
        """
        Checks wether the sequence can be built, i.e. wether all elements
        have waveforms on the same channels and of the same length.
        """
        # TODO: Give helpful info if the check fails

        try:
            self._awgspecs['SR']
        except KeyError:
            raise KeyError('No sample rate specified. Can not perform check')

        # First check that all sample rates agree
        # Since all elements are validated on input, the SR exists
        SRs = [elem.SR for elem in self._data.values()]
        if SRs == []:  # case of empty Sequence
            SRs = [None]
        if SRs.count(SRs[0]) != len(SRs):
            failmssg = ('checkConsistency failed: inconsistent sample rates.')
            log.info(failmssg)
            if verbose:
                print(failmssg)
            return False

        # Then check that elements use the same channels
        specchans = []
        for elem in self._data.values():
            chans = sorted(elem.channels)
            specchans.append(chans)
        if specchans == []:  # case of empty Sequence
            chans = None
            specchans = [None]
        if specchans.count(chans) != len(specchans):
            failmssg = ('checkConsistency failed: different elements specify '
                        'different channels')
            log.info(failmssg)
            if verbose:
                print(failmssg)
            return False

        # TODO: must all elements have same length? Does any AWG require this?

        # Finally, check that all positions are filled
        positions = list(self._data.keys())
        if positions == []:  # case of empty Sequence
            positions = [1]
        if not positions == list(range(1, len(positions)+1)):
            failmssg = ('checkConsistency failed: inconsistent sequence'
                        'positions. Must be 1, 2, 3, ...')
            log.info(failmssg)
            if verbose:
                print(failmssg)
            return False

        # If all three tests pass...
        return True

    @property
    def description(self):
        """
        Return a dictionary fully describing the Sequence.
        """
        desc = {}

        for pos, elem in self._data.items():
            desc[str(pos)] = {}
            desc[str(pos)]['channels'] = elem.description
            try:
                sequencing = self._sequencing[pos]
                seqdict = {'Wait trigger': sequencing[0],
                           'Repeat': sequencing[1],
                           'Event jump to': sequencing[2],
                           'Go to': sequencing[3]}
                desc[str(pos)]['sequencing'] = seqdict
            except KeyError:
                desc[str(pos)]['sequencing'] = 'Not set'

        return desc

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, newname):
        if not isinstance(newname, str):
            raise ValueError('The sequence name must be a string')
        self._name = newname

    @property
    def length_sequenceelements(self):
        """
        Returns the current number of specified sequence elements
        """
        return len(self._data)

    @property
    def SR(self):
        """
        Returns the sample rate, if defined. Else returns -1.
        """
        try:
            SR = self._awgspecs['SR']
        except KeyError:
            SR = -1

        return SR

    @property
    def channels(self):
        """
        Returns a list of the specified channels
        """
        return self.element(1).channels

    def element(self, pos):
        """
        Returns the element at the given position. Changes made to the return
        value of this methods will apply to the sequence. If this is undesired,
        make a copy of the returned element using Element.copy

        Args:
            pos (int): The sequence position

        Raises:
            KeyError: If no element is specified at the given position
        """
        try:
            elem = self._data[pos]
        except KeyError:
            raise KeyError('No element specified at sequence '
                           'position {}'.format(pos))

        return elem

    def plotSequence(self):
        """
        Visualise the sequence

        """
        if not self.checkConsistency():
            raise ValueError('Can not plot sequence: Something is '
                             'inconsistent. Please run '
                             'checkConsistency(verbose=True) for more details')

        # First forge all elements that are blueprints
        seqlen = self.length_sequenceelements
        elements = []
        for pos in range(1, seqlen+1):
            rawelem = self._data[pos]
            # returns the elements as dicts with
            # {channel: [wfm, m1, m2, time, newdurations]} structure
            elements.append(rawelem.getArrays())

        self._plotSequence(elements)

    def plotAWGOutput(self):
        """
        Plot the actual output for an AWG. If not delays or filter
        compensations are specified, this does the same as
        plotSequence.
        """

        package = self.outputForAWGFile()

        elements = []

        def rescaler(val, ampl, off):
            return ampl*(val+off)/2

        for pos in range(self.length_sequenceelements):
            element = {}
            for chanind, chan in enumerate(self.channels):
                npts = len(package[chanind][0][0][pos])

                keystr_a = 'channel{}_amplitude'.format(chan)
                keystr_o = 'channel{}_offset'.format(chan)
                amp = self._awgspecs[keystr_a]
                off = self._awgspecs[keystr_o]

                wfm_raw = package[chanind][0][0][pos]  # values from -1 to 1
                wfm = rescaler(wfm_raw, amp, off)

                element[chan] = [wfm,
                                 package[chanind][1][0][pos],  # m1
                                 package[chanind][2][0][pos],  # m2
                                 np.linspace(0, npts/self.SR, npts)  # time
                                 ]
            elements.append(element)

        self._plotSequence(elements)

    def _plotSequence(self, elements):
        """
        The heavy lifting plotter
        """

        # Get the dimensions.
        chans = self._data[1].channels  # All element have the same channels
        seqlen = self.length_sequenceelements

        # Then figure out the figure scalings
        chanminmax = [[np.inf, -np.inf]]*len(chans)
        for chanind, chan in enumerate(chans):
            for pos in range(seqlen):
                wfmdata = elements[pos][chan][0]
                (thismin, thismax) = (wfmdata.min(), wfmdata.max())
                if thismin < chanminmax[chanind][0]:
                    chanminmax[chanind] = [thismin, chanminmax[chanind][1]]
                if thismax > chanminmax[chanind][1]:
                    chanminmax[chanind] = [chanminmax[chanind][0], thismax]

        fig, axs = plt.subplots(len(chans), seqlen)

        # ...and do the plotting
        for chanind, chan in enumerate(chans):

            # figure out the channel voltage scaling
            # The entire channel shares a y-axis
            v_max = max([elements[pp][chan][0].max() for pp in range(seqlen)])
            voltageexponent = np.log10(v_max)
            voltageunit = 'V'
            voltagescaling = 1
            if voltageexponent < 0:
                voltageunit = 'mV'
                voltagescaling = 1e3
            if voltageexponent < -3:
                voltageunit = 'micro V'
                voltagescaling = 1e6
            if voltageexponent < -6:
                voltageunit = 'nV'
                voltagescaling = 1e9

            for pos in range(seqlen):
                # 1 by N arrays are indexed differently than M by N arrays
                # and 1 by 1 arrays are not arrays at all...
                if len(chans) == 1 and seqlen > 1:
                    ax = axs[pos]
                if len(chans) > 1 and seqlen == 1:
                    ax = axs[chanind]
                if len(chans) == 1 and seqlen == 1:
                    ax = axs
                if len(chans) > 1 and seqlen > 1:
                    ax = axs[chanind, pos]

                # reduce the tickmark density (must be called before scaling)
                ax.locator_params(tight=True, nbins=4, prune='lower')

                wfm = elements[pos][chan][0]
                m1 = elements[pos][chan][1]
                m2 = elements[pos][chan][2]
                time = elements[pos][chan][3]
                # get the durations if they are specified
                try:
                    newdurs = elements[pos][chan][4]
                except IndexError:
                    newdurs = []

                # Figure out the axes' scaling
                timeexponent = np.log10(time.max())
                timeunit = 's'
                timescaling = 1
                if timeexponent < 0:
                    timeunit = 'ms'
                    timescaling = 1e3
                if timeexponent < -3:
                    timeunit = 'micro s'
                    timescaling = 1e6
                if timeexponent < -6:
                    timeunit = 'ns'
                    timescaling = 1e9

                # waveform
                ax.plot(timescaling*time, voltagescaling*wfm, lw=3,
                        color=(0.6, 0.4, 0.3), alpha=0.4)
                ymax = voltagescaling * chanminmax[chanind][1]
                ymin = voltagescaling * chanminmax[chanind][0]
                yrange = ymax - ymin
                ax.set_ylim([ymin-0.05*yrange, ymax+0.2*yrange])

                # marker1 (red, on top)
                y_m1 = ymax+0.15*yrange
                marker_on = np.ones_like(m1)
                marker_on[m1 == 0] = np.nan
                marker_off = np.ones_like(m1)
                ax.plot(timescaling*time, y_m1*marker_off,
                        color=(0.6, 0.1, 0.1), alpha=0.2, lw=2)
                ax.plot(timescaling*time, y_m1*marker_on,
                        color=(0.6, 0.1, 0.1), alpha=0.6, lw=2)

                # marker 2 (blue, below the red)
                y_m2 = ymax+0.10*yrange
                marker_on = np.ones_like(m2)
                marker_on[m2 == 0] = np.nan
                marker_off = np.ones_like(m2)
                ax.plot(timescaling*time, y_m2*marker_off,
                        color=(0.1, 0.1, 0.1), alpha=0.2, lw=2)
                ax.plot(timescaling*time, y_m2*marker_on,
                        color=(0.1, 0.1, 0.6), alpha=0.6, lw=2)

                # time step lines
                for dur in np.cumsum(newdurs):
                    ax.plot([timescaling*dur, timescaling*dur],
                            [ax.get_ylim()[0], ax.get_ylim()[1]],
                            color=(0.312, 0.2, 0.33),
                            alpha=0.3)

                # labels
                if pos == 0:
                    ax.set_ylabel('({})'.format(voltageunit))
                if pos == seqlen - 1:
                    newax = ax.twinx()
                    newax.set_yticks([])
                    newax.set_ylabel('Ch. {}'.format(chan))
                ax.set_xlabel('({})'.format(timeunit))

                # remove excess space from the plot
                if not chanind+1 == len(chans):
                    ax.set_xticks([])
                if not pos == 0:
                    ax.set_yticks([])
                fig.subplots_adjust(hspace=0, wspace=0)

                # display sequencer information
                if chanind == 0:
                    seq_info = self._sequencing[pos+1]
                    titlestring = ''
                    if seq_info['twait'] == 1:  # trigger wait
                        titlestring += 'T '
                    if seq_info['nrep'] > 1:  # nreps
                        titlestring += '\u21BB{} '.format(seq_info[1])
                    if seq_info['nrep'] == 0:
                        titlestring += '\u221E '
                    if seq_info['jump_input'] != 0:
                        if seq_info['jump_input'] == -1:
                            titlestring += 'E\u2192 '
                        else:
                            titlestring += 'E{} '.format(seq_info[2])
                    if seq_info['goto'] > 0:
                        titlestring += '\u21b1{}'.format(seq_info[3])

                    ax.set_title(titlestring)

    def _prepareForOutputting(self) -> List[Dict[int, np.ndarray]]:
        """
        The preparser for numerical output. Applies delay and ripasso
        corrections.

        Returns:
            A list of outputs of the Element's getArrays functions, i.e.
                a list of dictionaries with key position (int) and value
                an np.ndarray of array([wfm, m1, m2, time]), where the
                wfm values are still in V. The particular backend output
                function must rescale to the specific format it adheres to.
        """
        # Validation
        if not self.checkConsistency():
            raise ValueError('Can not generate output. Something is '
                             'inconsistent. Please run '
                             'checkConsistency(verbose=True) for more details')
        #
        #
        channels = self.element(1).channels  # all elements have ident. chans
        # We copy the data so that the state of the Sequence is left unaltered
        # by outputting for AWG
        data = deepcopy(self._data)
        seqlen = len(data.keys())
        # check if sequencing information is specified for each element
        if not sorted(list(self._sequencing.keys())) == list(range(1, seqlen+1)):
            raise ValueError('Can not generate output for .awg file; '
                             'incorrect sequencer information.')

        # Verify physical amplitude specifiations
        for chan in channels:
            ampkey = 'channel{}_amplitude'.format(chan)
            if ampkey not in self._awgspecs.keys():
                raise KeyError('No amplitude specified for channel '
                               '{}. Can not continue.'.format(chan))

        # Apply channel delays. This is most elegantly done before forging.
        # Add waituntil at the beginning, update all waituntils inside, add a
        # zeros segment at the end.
        # If already-forged arrays are found, simply append and prepend zeros
        delays = []
        for chan in channels:
            try:
                delays.append(self._awgspecs['channel{}_delay'.format(chan)])
            except KeyError:
                delays.append(0)
        maxdelay = max(delays)

        for pos in range(1, seqlen+1):
            for chanind, chan in enumerate(channels):
                element = data[pos]
                delay = delays[chanind]

                if 'blueprint' in element._data[chan].keys():
                    blueprint = element._data[chan]['blueprint']

                    # update existing waituntils
                    for segpos in range(len(blueprint._funlist)):
                        if blueprint._funlist[segpos] == 'waituntil':
                            oldwait = blueprint._argslist[segpos][0]
                            blueprint._argslist[segpos] = (oldwait+delay,)
                    # insert delay before the waveform
                    if delay > 0:
                        blueprint.insertSegment(0, 'waituntil', (delay,),
                                                'waituntil')
                    # add zeros at the end
                    if maxdelay-delay > 0:
                        blueprint.insertSegment(-1, PulseAtoms.ramp, (0, 0),
                                                dur=maxdelay-delay)
                    # TODO: is the next line even needed?
                    element.addBluePrint(chan, blueprint)

                else:
                    arrays = element[chan]['array']
                    for ii, arr in enumerate(arrays):
                        pre_wait = np.zeros(int(delay/self.SR))
                        post_wait = np.zeros(int((maxdelay-delay)/self.SR))
                        arrays[ii] = np.concatenate((pre_wait, arr, post_wait))

        # Now forge all the elements as specified
        elements = []  # the forged elements
        for pos in range(1, seqlen+1):
            elements.append(data[pos].getArrays())

        # Now that the numerical arrays exist, we can apply filter compensation
        for chan in channels:
            keystr = 'channel{}_filtercompensation'.format(chan)
            if keystr in self._awgspecs.keys():
                kind = self._awgspecs[keystr]['kind']
                order = self._awgspecs[keystr]['order']
                f_cut = self._awgspecs[keystr]['f_cut']
                tau = self._awgspecs[keystr]['tau']
                if f_cut is None:
                    f_cut = 1/tau
                for pos in range(seqlen):
                    prefilter = elements[pos][chan][0]
                    postfilter = applyInverseRCFilter(prefilter,
                                                      self.SR,
                                                      kind, f_cut, order,
                                                      DCgain=1)
                    elements[pos][chan][0] = postfilter

        return elements

    def outputForSEQXFile(self) -> Tuple[List[int], List[int], List[int],
                                         List[int], List[int],
                                         List[List[np.ndarray]],
                                         List[float], str]:
        """
        Generate a tuple matching the call signature of the QCoDeS
        AWG70000A driver's `makeSEQXFile` function. If channel delays
        have been specified, they are added to the ouput before exporting.
        The intended use of this function together with the QCoDeS driver is

        .. code:: python

            pkg = seq.outputForSEQXFile()
            seqx = awg70000A.makeSEQXFile(*pkg)

        Returns:
            A tuple holding (trig_waits, nreps, event_jumps, event_jump_to,
                go_to, wfms, amplitudes, seqname)
        """

        # most of the footwork is done by the following function
        elements = self._prepareForOutputting()
        # _prepareForOutputting asserts that channel amplitudes and
        # full sequencing is specified
        seqlen = len(elements)
        # all elements have ident. chans since _prepareForOutputting
        # did not raise an exception
        channels = self.element(1).channels

        for chan in channels:
            offkey = 'channel{}_offset'.format(chan)
            if offkey in self._awgspecs.keys():
                log.warning("Found a specified offset for channel "
                            "{}, but .seqx files can't contain offset "
                            "information. Will ignore the offset."
                            "".format(chan))

        # now check that the amplitudes are within the allowed limits
        # also verify that all waveforms are at least 2400 points
        # No rescaling because the driver's _makeWFMXBinaryData does
        # the rescaling

        amplitudes = []
        for chan in channels:
            ampl = self._awgspecs['channel{}_amplitude'.format(chan)]
            amplitudes.append(ampl)
        if len(amplitudes) == 1:
            amplitudes.append(0)

        for pos in range(1, seqlen+1):
            element = elements[pos-1]
            for chan in channels:
                ampl = self._awgspecs['channel{}_amplitude'.format(chan)]
                wfm = element[chan][0]
                # check the waveform length
                if len(wfm) < 2400:
                    raise ValueError('Waveform too short on channel '
                                     '{} at step {}; only {} points. '
                                     'The required minimum is 2400 points.'
                                     ''.format(chan, pos, len(wfm)))
                # check whether the waveform voltages can be realised
                if wfm.max() > ampl/2:
                    raise ValueError('Waveform voltages exceed channel range '
                                     'on channel {}'.format(chan) +
                                     ' sequence element {}.'.format(pos) +
                                     ' {} > {}!'.format(wfm.max(), ampl/2))
                if wfm.min() < -ampl/2:
                    raise ValueError('Waveform voltages exceed channel range '
                                     'on channel {}'.format(chan) +
                                     ' sequence element {}. '.format(pos) +
                                     '{} < {}!'.format(wfm.min(), -ampl/2))
                element[chan][0] = wfm
            elements[pos-1] = element

        # Finally cast the lists into the shapes required by the AWG driver

        waveforms = cast(List[List[np.ndarray]],
                         [[] for dummy in range(len(channels))])
        nreps = []
        trig_waits = []
        gotos = []
        jump_states = []
        jump_tos = []

        # Since sequencing options are valid/invalid differently for
        # different backends, we make the validation here
        for pos in range(1, seqlen+1):
            for chanind, chan in enumerate(channels):
                wfm = elements[pos-1][chan][0]
                m1 = elements[pos-1][chan][1]
                m2 = elements[pos-1][chan][2]
                waveforms[chanind].append(np.array([wfm, m1, m2]))

            twait = self._sequencing[pos]['twait']
            nrep = self._sequencing[pos]['nrep']
            jump_to = self._sequencing[pos]['jump_target']
            jump_state = self._sequencing[pos]['jump_input']
            goto = self._sequencing[pos]['goto']

            if twait not in [0, 1, 2, 3]:
                raise SequencingError('Invalid trigger input at position'
                                      '{}: {}. Must be 0, 1, 2, or 3.'
                                      ''.format(pos, twait))

            if jump_state not in [0, 1, 2, 3]:
                raise SequencingError('Invalid event jump input at position'
                                      '{}: {}. Must be either 0, 1, 2, or 3.'
                                      ''.format(pos, twait))

            if nrep not in range(0, 16384):
                raise SequencingError('Invalid number of repetions at position'
                                      '{}: {}. Must be either 0 (infinite) '
                                      'or 1-16,383.'.format(pos, nrep))

            if jump_to not in range(-1, seqlen+1):
                raise SequencingError('Invalid event jump target at position'
                                      '{}: {}. Must be either -1 (next),'
                                      ' 0 (off), or 1-{}.'
                                      ''.format(pos, jump_to, seqlen))

            if goto not in range(0, seqlen+1):
                raise SequencingError('Invalid goto target at position'
                                      '{}: {}. Must be either 0 (next),'
                                      ' or 1-{}.'
                                      ''.format(pos, goto, seqlen))

            trig_waits.append(twait)
            nreps.append(nrep)
            jump_tos.append(jump_to)
            jump_states.append(jump_state)
            gotos.append(goto)

        return (trig_waits, nreps, jump_states, jump_tos, gotos,
                waveforms, amplitudes, self.name)

    def outputForAWGFile(self):
        """
        Returns a sliceable object with items matching the call
        signature of the 'make_*_awg_file' functions of the QCoDeS
        AWG5014 driver. One may then construct an awg file as follows
        (assuming that seq is the sequence object):

        .. code:: python

            package = seq.outputForAWGFile()
            make_awg_file(*package[:], **kwargs)


        """

        elements = self._prepareForOutputting()
        seqlen = len(elements)
        # all elements have ident. chans since _prepareForOutputting
        # did not raise an exception
        channels = self.element(1).channels

        for chan in channels:
            offkey = 'channel{}_offset'.format(chan)
            if offkey not in self._awgspecs.keys():
                raise ValueError("No specified offset for channel "
                                 "{}, can not continue."
                                 "".format(chan))

        # Apply channel scaling
        # We must rescale to the interval -1, 1 where 1 is ampl/2+off and -1 is
        # -ampl/2+off.
        #
        def rescaler(val, ampl, off):
            return val/ampl*2-off
        for pos in range(1, seqlen+1):
            element = elements[pos-1]
            for chan in channels:
                ampl = self._awgspecs['channel{}_amplitude'.format(chan)]
                off = self._awgspecs['channel{}_offset'.format(chan)]
                wfm = element[chan][0]
                # check whether the waveform voltages can be realised
                if wfm.max() > ampl/2+off:
                    raise ValueError('Waveform voltages exceed channel range '
                                     'on channel {}'.format(chan) +
                                     ' sequence element {}.'.format(pos) +
                                     ' {} > {}!'.format(wfm.max(), ampl/2+off))
                if wfm.min() < -ampl/2+off:
                    raise ValueError('Waveform voltages exceed channel range '
                                     'on channel {}'.format(chan) +
                                     ' sequence element {}. '.format(pos) +
                                     '{} < {}!'.format(wfm.min(), -ampl/2+off))
                wfm = rescaler(wfm, ampl, off)
                element[chan][0] = wfm
            elements[pos-1] = element

        # Finally cast the lists into the shapes required by the AWG driver
        waveforms = [[] for dummy in range(len(channels))]
        m1s = [[] for dummy in range(len(channels))]
        m2s = [[] for dummy in range(len(channels))]
        nreps = []
        trig_waits = []
        gotos = []
        jump_tos = []

        # Since sequencing options are valid/invalid differently for
        # different backends, we make the validation here
        for pos in range(1, seqlen+1):
            for chanind, chan in enumerate(channels):
                waveforms[chanind].append(elements[pos-1][chan][0])
                m1s[chanind].append(elements[pos-1][chan][1])
                m2s[chanind].append(elements[pos-1][chan][2])

            twait = self._sequencing[pos]['twait']
            nrep = self._sequencing[pos]['nrep']
            jump_to = self._sequencing[pos]['jump_target']
            goto = self._sequencing[pos]['goto']

            if twait not in [0, 1]:
                raise SequencingError('Invalid trigger wait state at position'
                                      '{}: {}. Must be either 0 or 1.'
                                      ''.format(pos, twait))

            if nrep not in range(0, 65537):
                raise SequencingError('Invalid number of repetions at position'
                                      '{}: {}. Must be either 0 (infinite) '
                                      'or 1-65,536.'.format(pos, nrep))

            if jump_to not in range(-1, seqlen+1):
                raise SequencingError('Invalid event jump target at position'
                                      '{}: {}. Must be either -1 (next),'
                                      ' 0 (off), or 1-{}.'
                                      ''.format(pos, jump_to, seqlen))

            if goto not in range(0, seqlen+1):
                raise SequencingError('Invalid goto target at position'
                                      '{}: {}. Must be either 0 (next),'
                                      ' or 1-{}.'
                                      ''.format(pos, goto, seqlen))

            trig_waits.append(twait)
            nreps.append(nrep)
            jump_tos.append(jump_to)
            gotos.append(goto)

        # ...and make a sliceable object out of them
        output = _AWGOutput((waveforms, m1s, m2s, nreps,
                             trig_waits, gotos,
                             jump_tos), self.channels)

        return output


def _subelementBuilder(blueprint: BluePrint, SR: int,
                       durs: List[float]) -> Tuple[np.ndarray, List[float]]:
    """
    The function building a blueprint, returning a numpy array.

    This is the core translater from description of pulse to actual data points
    All arrays must be made with this function
    """

    # Important: building the element must NOT modify any of the mutable
    # inputs, therefore all lists are copied
    funlist = blueprint._funlist.copy()
    argslist = blueprint._argslist.copy()
    namelist = blueprint._namelist.copy()
    marker1 = blueprint.marker1.copy()
    marker2 = blueprint.marker2.copy()
    segmark1 = blueprint._segmark1.copy()
    segmark2 = blueprint._segmark2.copy()

    durations = durs.copy()

    no_of_waits = funlist.count('waituntil')

    # handle waituntil by translating it into a normal function
    waitpositions = [ii for ii, el in enumerate(funlist) if el == 'waituntil']

    # Calculate elapsed times

    for nw in range(no_of_waits):
        pos = waitpositions[nw]
        funlist[pos] = PulseAtoms.waituntil
        elapsed_time = sum(durations[:pos])
        wait_time = argslist[pos][0]
        dur = wait_time - elapsed_time
        if dur < 0:
            raise ValueError('Inconsistent timing. Can not wait until ' +
                             '{} at position {}.'.format(wait_time, pos) +
                             ' {} elapsed already'.format(elapsed_time))
        else:
            durations[pos] = dur

    # When special segments like 'waituntil' and 'ensureaverage' get
    # evaluated, the list of durations gets updated. That new list
    # is newdurations
    newdurations = durations

    # All waveforms must ultimately have an integer number of samples
    # Now figure out from the durations what these integers are
    #
    # The most honest thing to do is to simply round off dur*SR
    # and raise an exception if the segment ends up with less than
    # two points

    intdurations = np.zeros(len(newdurations))

    for ii, dur in enumerate(newdurations):
        int_dur = round(dur*SR)
        if int_dur < 2:
            raise SegmentDurationError('Too short segment detected! '
                                       'Segment "{}" at position {} '
                                       'has a duration of {} which at '
                                       'an SR of {:.3E} leads to just {} '
                                       'points(s). There must be at least '
                                       '2 points in each segment.'
                                       ''.format(namelist[ii],
                                                 ii,
                                                 newdurations[ii],
                                                 SR,
                                                 int_dur))
        else:
            intdurations[ii] = int_dur
            newdurations[ii] = int_dur/SR

    # The actual forging of the waveform
    parts = [ft.partial(fun, *args) for (fun, args) in zip(funlist, argslist)]
    blocks = [list(p(SR, d)) for (p, d) in zip(parts, intdurations)]
    output = [block for sl in blocks for block in sl]

    # now make the markers
    time = np.linspace(0, sum(newdurations), len(output))
    m1 = np.zeros_like(time)
    m2 = m1.copy()
    dt = time[1] - time[0]
    # update the 'absolute time' marker list with 'relative time'
    # (segment bound) markers converted to absolute time
    elapsed_times = np.cumsum([0.0] + newdurations)
    for pos, spec in enumerate(segmark1):
        if spec[1] is not 0:
            ontime = elapsed_times[pos] + spec[0]  # spec is (delay, duration)
            marker1.append((ontime, spec[1]))
    for pos, spec in enumerate(segmark2):
        if spec[1] is not 0:
            ontime = elapsed_times[pos] + spec[0]  # spec is (delay, duration)
            marker2.append((ontime, spec[1]))
    msettings = [marker1, marker2]
    marks = [m1, m2]
    for marker, setting in zip(marks, msettings):
        for (t, dur) in setting:
            ind = np.abs(time-t).argmin()
            chunk = int(np.round(dur/dt))
            marker[ind:ind+chunk] = 1

    output = np.array(output)  # TODO: Why is this sometimes needed?

    return np.array([output, m1, m2, time]), newdurations


def elementBuilder(blueprints, SR, durations, channels=None,
                   returnnewdurs=False):
    """
    Forge blueprints into an element

    Args:
        blueprints (Union[BluePrint, list]): A single blueprint or a list of
            blueprints.
        SR (int): The sample rate (Sa/s)
        durations (list): List of durations or a list of lists of durations
            if different blueprints have different durations. If a single list
            is given, this list is used for all blueprints.
        channels (Union[list, None]): A list specifying the channels of the
            blueprints in the list. If None, channels 1, 2, .. are assigned
        returnnewdurs (bool): If True, the returned dictionary contains the
            newdurations.

    Returns:
        dict:
            Dictionary with channel numbers (ints) as keys and forged
            blueprints as values. A forged blueprint is a numpy array
            given by np.array([wfm, m1, m2, time]). If returnnewdurs is True,
            a list of [wfm, m1, m2, time, newdurs] is returned instead.

    Raises:
        ValueError: if blueprints does not contain BluePrints
        ValueError: if the wrong number of blueprints/durations is given
    """

    # Validation
    if not (isinstance(blueprints, BluePrint) or isinstance(blueprints, list)):
        raise ValueError('blueprints must be a BluePrint object or a list of '
                         'BluePrint objects. '
                         'Received {}.'.format(type(blueprints)))
    if isinstance(blueprints, BluePrint):
        blueprints = [blueprints]
    # Allow for using a single durations list for all blueprints
    if not isinstance(durations[0], list):
        durations = [durations]*len(blueprints)
        # durations = [durations for _ in range(len(blueprints))]

    if channels is None:
        channels = [ii for ii in range(len(blueprints))]

    bpdurs = zip(blueprints, durations)
    if not returnnewdurs:
        subelems = [_subelementBuilder(bp, SR, dur)[0] for (bp, dur) in bpdurs]
    else:
        subelems = []
        for (bp, dur) in bpdurs:
            subelems.append(list(_subelementBuilder(bp, SR, dur)[0]) +
                            [_subelementBuilder(bp, SR, dur)[1]])

    outdict = dict(zip(channels, subelems))

    return outdict


def bluePrintPlotter(blueprints, fig=None, axs=None):
    """
    Plots a bluePrint or list of blueprints for easy overview.

    Args:
        blueprints (Union[BluePrint, list[BluePrint]]): A single BluePrint or a
            list of blueprints to plot.
        fig (Union[matplotlib.figure.Figure, None]): The figure on which to
            plot. If None is given, a new instance is created.
        axs (Union[list, None]): A list of
            matplotlib.axes._subplots.AxesSubplot to plot onto. If None is
            given, a new list is created.
    """

    #  Todo: All sorts of validation on lengths of blueprint and the like

    # Allow single blueprint
    if not isinstance(blueprints, list):
        blueprints = [blueprints]

    SRs = []
    for blueprint in blueprints:
        if blueprint.SR is None:
            raise ValueError('No sample rate specified for blueprint.'
                             ' Can not create plot. Please specify a'
                             ' sample rate.')
        else:
            SRs.append(blueprint.SR)

    if len(set(SRs)) != 1:
        raise ValueError('Blueprints do not have matching sample '
                         'rates. Received {}. Can not proceed.'
                         ''.format(SRs))
    else:
        SR = SRs[0]

    durations = []
    for blueprint in blueprints:
        durations.append(blueprint._durslist)

    if fig is None:
        fig = plt.figure()
    N = len(blueprints)

    if axs is None:
        axs = [fig.add_subplot(N, 1, ii+1) for ii in range(N)]

    for ii in range(N):
        ax = axs[ii]
        arrays, newdurs = _subelementBuilder(blueprints[ii], SR,
                                             durations[ii])
        wfm = arrays[0, :]
        m1 = arrays[1, :]
        m2 = arrays[2, :]
        time = np.linspace(0, np.sum(newdurs), len(wfm))

        # Figure out time axis scaling
        exponent = np.log10(time.max())
        timeunit = 's'
        timescaling = 1
        if exponent < 0:
            timeunit = 'ms'
            timescaling = 1e3
        if exponent < -3:
            timeunit = 'micro s'  # sadly, we don't live in the global future..
            timescaling = 1e6
        if exponent < -6:
            timeunit = 'ns'
            timescaling = 1e9

        # Figure out voltage axis scaling
        exponent = np.log10(wfm.max())
        voltageunit = 'V'
        voltagescaling = 1
        if exponent < 0:
            voltageunit = 'mV'
            voltagescaling = 1e3
        if exponent < -3:
            voltageunit = 'micro V'
            voltagescaling = 1e6
        if exponent < -6:
            voltageunit = 'nV'
            voltagescaling = 1e9

        ax.locator_params(tight=True, nbins=3, prune='lower')

        yrange = voltagescaling * (wfm.max() - wfm.min())
        ax.set_ylim([voltagescaling*wfm.min()-0.05*yrange,
                     voltagescaling*wfm.max()+0.2*yrange])

        # PLOT lines indicating the durations
        for dur in np.cumsum(newdurs):
            ax.plot([dur*timescaling, dur*timescaling],
                    [ax.get_ylim()[0], ax.get_ylim()[1]],
                    color=(0.312, 0.2, 0.33),
                    alpha=0.3)

        # plot the waveform
        ax.plot(timescaling*time, voltagescaling*wfm,
                lw=3, color=(0.6, 0.4, 0.3), alpha=0.4)

        # plot the markers
        y_m1 = (voltagescaling*wfm.max()+0.15*yrange)
        marker_on = np.ones_like(m1)
        marker_on[m1 == 0] = np.nan
        marker_off = np.ones_like(m1)
        ax.plot(time*timescaling, y_m1*marker_off,
                color=(0.6, 0.1, 0.1), alpha=0.2, lw=2)
        ax.plot(time*timescaling, y_m1*marker_on,
                color=(0.6, 0.1, 0.1), alpha=0.6, lw=2)
        #
        y_m2 = voltagescaling*wfm.max()+0.10*yrange
        marker_on = np.ones_like(m2)
        marker_on[m2 == 0] = np.nan
        marker_off = np.ones_like(m2)
        ax.plot(time*timescaling, y_m2*marker_off,
                color=(0.1, 0.1, 0.6), alpha=0.2, lw=2)
        ax.plot(time*timescaling, y_m2*marker_on,
                color=(0.1, 0.1, 0.6), alpha=0.6, lw=2)

    # Prettify a bit
    for ax in axs[:-1]:
        ax.set_xticks([])
    axs[-1].set_xlabel('Time ({})'.format(timeunit))
    for ax in axs:
        ax.set_ylabel('Signal ({})'.format(voltageunit))
    fig.subplots_adjust(hspace=0)


def makeLinearlyVaryingSequence(baseelement, channel, name, arg, start, stop,
                                step):
    """
    Make a pulse sequence where a single parameter varies linearly.
    The pulse sequence will consist of N copies of the same element with just
    the specified argument changed (N = abs(stop-start)/steps)

    Args:
        baseelement (Element): The basic element.
        channel (int): The channel where the change should happen
        name (str): Name of the blueprint segment to change
        arg (Union[str, int]): Name (str) or position (int) of the argument
            to change. If the arg is 'duration', the duration is changed
            instead.
        start (float): Start point of the variation (included)
        stop (float): Stop point of the variation (included)
        step (float): Increment of the variation
    """

    # TODO: validation
    # TODO: Make more general varyer and refactor code

    sequence = Sequence()

    sequence.setSR(baseelement.SR)

    iterator = np.linspace(start, stop, round(abs(stop-start)/step)+1)

    for ind, val in enumerate(iterator):
        element = baseelement.copy()
        if arg == 'duration':
            element.changeDuration(channel, name, val)
        else:
            element.changeArg(channel, name, arg, val)
        sequence.addElement(ind+1, element)

    return sequence


def makeVaryingSequence(baseelement, channels, names, args, iters):
    """
    Make a pulse sequence where N parameters vary simultaneously in M steps.
    The user inputs a baseelement which is copied M times and changed
    according to the given inputs.

    Args:
        baseelement (Element): The basic element.
        channels (Union[list, tuple]): Either a list or a tuple of channels on
            which to find the blueprint to change. Must have length N.
        names (Union[list, tuple]): Either a list or a tuple of names of the
            segment to change. Must have length N.
        args (Union[list, tuple]): Either a list or a tuple of argument
            specifications for the argument to change. Use 'duration' to change
            the segment duration. Must have length N.
        iters (Union[list, tuple]): Either a list or a tuple of length N
            containing Union[list, tuple, range] of length M.

    Raises:
        ValueError: If not channels, names, args, and iters are of the same
            length.
        ValueError: If not each iter in iters specifies the same number of
            values.
    """

    # Validation
    baseelement.validateDurations()

    inputlengths = [len(channels), len(names), len(args), len(iters)]
    if not inputlengths.count(inputlengths[0]) == len(inputlengths):
        raise ValueError('Inconsistent number of channel, names, args, and '
                         'parameter sequences. Please specify the same number '
                         'of each.')
    noofvals = [len(itr) for itr in iters]
    if not noofvals.count(noofvals[0]) == len(iters):
        raise ValueError('Not the same number of values in each parameter '
                         'value sequence (input argument: iters)')

    sequence = Sequence()
    sequence.setSR(baseelement.SR)

    for elnum in range(1, noofvals[0]+1):
        sequence.addElement(elnum, baseelement.copy())

    for (chan, name, arg, vals) in zip(channels, names, args, iters):
        for mpos, val in enumerate(vals):
            element = sequence.element(mpos+1)
            if arg == 'duration':
                element.changeDuration(chan, name, val)
            else:
                element.changeArg(chan, name, arg, val)

    log.info('Created varying sequence using makeVaryingSequence.'
             ' Now validating it...')

    if not sequence.checkConsistency():
        raise SequenceConsistencyError('Invalid sequence. See log for '
                                       'details.')
    else:
        log.info('Valid sequence')
        return sequence


def repeatAndVarySequence(seq, poss, channels, names, args, iters):
    """
    Repeat a sequence and vary part(s) of it. Returns a new sequence.
    Given N specifications of M steps, N parameters are varied in M
    steps.

    Args:
        seq (Sequence): The sequence to be repeated.
        poss (Union[list, tuple]): A length N list/tuple specifying at which
            sequence position(s) the blueprint to change is.
        channels (Union[list, tuple]): A length N list/tuple specifying on
            which channel(s) the blueprint to change is.
        names (Union[list, tuple]): A length N list/tuple specifying the name
            of the segment to change.
        args (Union[list, tuple]): A length N list/tuple specifying which
            argument to change. A valid argument is also 'duration'.
        iters (Union[list, tuple]): A length N list/tuple containing length
            M indexable iterables with the values to step through.
    """

    if not seq.checkConsistency():
        raise SequenceConsistencyError('Inconsistent input sequence! Can not '
                                       'proceed. Check all positions '
                                       'and channels.')

    inputlens = [len(poss), len(channels), len(names), len(args), len(iters)]
    if not inputlens.count(inputlens[0]) == len(inputlens):
        raise ValueError('Inconsistent number of position, channel, name, args'
                         ', and '
                         'parameter sequences. Please specify the same number '
                         'of each.')
    noofvals = [len(itr) for itr in iters]
    if not noofvals.count(noofvals[0]) == len(iters):
        raise ValueError('Not the same number of values in each parameter '
                         'value sequence (input argument: iters)')

    newseq = Sequence()
    newseq._awgspecs = seq._awgspecs

    no_of_steps = noofvals[0]

    for step in range(no_of_steps):
        tempseq = seq.copy()
        for (pos, chan, name, arg, vals) in zip(poss, channels, names,
                                                args, iters):
            element = tempseq.element(pos)
            val = vals[step]

            if arg == 'duration':
                element.changeDuration(chan, name, val)
            else:
                element.changeArg(chan, name, arg, val)
        newseq = newseq + tempseq

    return newseq

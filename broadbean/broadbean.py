import logging
import warnings
from typing import Tuple, List, Dict, cast, Union, Callable
from inspect import signature
from copy import deepcopy
import functools as ft

import numpy as np
import matplotlib.pyplot as plt


log = logging.getLogger(__name__)


class SegmentDurationError(Exception):
    pass


class ElementDurationError(Exception):
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
    def sine(freq, ampl, off, phase, SR, npts):
        time = np.linspace(0, npts/SR, npts, endpoint=False)
        freq *= 2*np.pi
        return (ampl*np.sin(freq*time+phase)+off)

    @staticmethod
    def ramp(start, stop, SR, npts):
        dur = npts/SR
        slope = (stop-start)/dur
        time = np.linspace(0, dur, npts, endpoint=False)
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
        time = np.linspace(0, dur, npts, endpoint=False)
        centre = dur/2
        baregauss = np.exp((-(time-mu-centre)**2/(2*sigma**2)))
        return ampl*baregauss+offset


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

    @marked_for_deletion(replaced_by='broadbean.plotting.plotter')
    def plot(self, SR=None):
        pass

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
        # 'array': a dict {'wfm': np.array} (other keys: 'm1', 'm2', etc)
        # 'SR': Sample rate. Used with array.
        #
        # Another dict is meta, which holds:
        # 'duration': duration in seconds of the entire element.
        # 'SR': sample rate of the element
        # These two values are added/updated upon validation of the durations

        self._data = {}
        self._meta = {}

    def addBluePrint(self, channel: Union[str, int],
                     blueprint: BluePrint) -> None:
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

    def addArray(self, channel: Union[int, str], waveform: np.ndarray,
                 SR: int, **kwargs) -> None:
        """
        Add an array of voltage value to the element on the specified channel.
        Overwrites whatever was there before. Markers can be specified via
        the kwargs, i.e. the kwargs must specify arrays of markers. The names
        can be 'm1', 'm2', 'm3', etc.

        Args:
            channel: The channel number
            waveform: The array of waveform values (V)
            SR: The sample rate in Sa/s
        """

        N = len(waveform)
        self._data[channel] = {}
        self._data[channel]['array'] = {}

        for name, array in kwargs.items():
            if len(array) != N:
                raise ValueError('Length mismatch between waveform and '
                                 f'array {name}. Must be same length')
            self._data[channel]['array'].update({name: array})

        self._data[channel]['array']['wfm'] = waveform
        self._data[channel]['SR'] = SR

    def validateDurations(self):
        """
        Check that all channels have the same specified duration, number of
        points and sample rate.
        """

        # pick out the channel entries
        channels = self._data.values()

        if len(channels) == 0:
            raise KeyError('Empty Element, nothing assigned')

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
                length = len(channel['array']['wfm'])/channel['SR']
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
                length = len(channel['array']['wfm'])
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

    def getArrays(self,
                  includetime: bool=False) -> Dict[int, Dict[str, np.ndarray]]:
        """
        Return arrays of the element. Heavily used by the Sequence.

        Args:
            includetime: Whether to include time arrays. They will have the key
                'time'. Time should be included when plotting, otherwise not.

        Returns:
            dict:
              Dictionary with channel numbers (ints) as keys and forged
              blueprints as values. A forged blueprint is a dict with
              the mandatory key 'wfm' and optional keys 'm1', 'm2', 'm3' (etc)
              and 'time'.

        """

        outdict = {}
        for channel, signal in self._data.items():
            if 'array' in signal.keys():
                outdict[channel] = signal['array']
                if includetime and 'time' not in signal['array'].keys():
                    N = len(signal['array']['wfm'])
                    dur = N/signal['SR']
                    outdict[channel]['array']['time'] = np.linspace(0, dur, N)
            elif 'blueprint' in signal.keys():
                bp = signal['blueprint']
                durs = bp.durations
                SR = bp.SR
                forged_bp = _subelementBuilder(bp, SR, durs)
                outdict[channel] = forged_bp
                if not includetime:
                    outdict[channel].pop('time')
                    outdict[channel].pop('newdurations')
                # TODO: should the be a separate bool for newdurations?

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
        for chan in channels:

            if not ('array' in chan.keys() or 'blueprint' in chan.keys()):
                raise ValueError('Neither BluePrint nor array assigned to '
                                 'chan {}!'.format(chan))
            if 'blueprint' in chan.keys():
                return chan['blueprint'].points
            else:
                return len(chan['array']['wfm'])

        else:
            # this line is here to make mypy happy; this exception is
            # already raised by validateDurations
            raise KeyError('Empty Element, nothing assigned')

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

    def changeArg(self, channel: Union[str, int],
                  name: str, arg: Union[str, int], value: Union[int, float],
                  replaceeverywhere: bool=False) -> None:
        """
        Change the argument of a function of the blueprint on the specified
        channel.

        Args:
            channel: The channel where the blueprint sits.
            name: The name of the segment in which to change an argument
            arg: Either the position (int) or name (str) of
                the argument to change
            value: The new value of the argument
            replaceeverywhere: If True, the same argument is overwritten
                in ALL segments where the name matches. E.g. 'gaussian1' will
                match 'gaussian', 'gaussian2', etc. If False, only the segment
                with exact name match gets a replacement.

        Raises:
            ValueError: If the specified channel has no blueprint.
            ValueError: If the argument can not be matched (either the argument
                name does not match or the argument number is wrong).
        """

        if channel not in self.channels:
            raise ValueError(f'Nothing assigned to channel {channel}')

        if 'blueprint' not in self._data[channel].keys():
            raise ValueError('No blueprint on channel {}.'.format(channel))

        bp = self._data[channel]['blueprint']

        bp.changeArg(name, arg, value, replaceeverywhere)

    def changeDuration(self, channel: Union[str, int], name: str,
                       newdur: Union[int, float],
                       replaceeverywhere: bool=False) -> None:
        """
        Change the duration of a segment of the blueprint on the specified
        channel

        Args:
            channel: The channel holding the blueprint in question
            name): The name of the segment to modify
            newdur: The new duration.
            replaceeverywhere: If True, all segments
                matching the base
                name given will have their duration changed. If False, only the
                segment with an exact name match will have its duration
                changed. Default: False.
        """

        if channel not in self.channels:
            raise ValueError(f'Nothing assigned to channel {channel}')

        if 'blueprint' not in self._data[channel].keys():
            raise ValueError('No blueprint on channel {}.'.format(channel))

        bp = self._data[channel]['blueprint']

        bp.changeDuration(name, newdur, replaceeverywhere)

    def _applyDelays(self, delays: List[float]) -> None:
        """
        Apply delays to the channels of this element. This function is intended
        to be used via a Sequence object. Note that this function changes
        the element it is called on. Calling _applyDelays a second will apply
        more delays on top of the first ones.

        Args:
            delays: A list matching the channels of the Element. If there
                are channels=[1, 3], then delays=[1e-3, 0] will delay channel
                1 by 1 ms and channel 3 by nothing.
        """
        if len(delays) != len(self.channels):
            raise ValueError('Incorrect number of delays specified.'
                             ' Must match the number of channels.')

        if not sum([d >= 0 for d in delays]) == len(delays):
            raise ValueError('Negative delays not allowed.')

        # The strategy is:
        # Add waituntil at the beginning, update all waituntils inside, add a
        # zeros segment at the end.
        # If already-forged arrays are found, simply append and prepend zeros

        SR = self.SR
        maxdelay = max(delays)

        for chanind, chan in enumerate(self.channels):
            delay = delays[chanind]

            if 'blueprint' in self._data[chan].keys():
                blueprint = self._data[chan]['blueprint']

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

            else:
                arrays = self._data[chan]['array']
                for name, arr in arrays.items():
                    pre_wait = np.zeros(int(delay*SR))
                    post_wait = np.zeros(int((maxdelay-delay)*SR))
                    arrays[name] = np.concatenate((pre_wait, arr, post_wait))

    def copy(self):
        """
        Return a copy of the element
        """
        new = Element()
        new._data = deepcopy(self._data)
        new._meta = deepcopy(self._meta)
        return new

    @marked_for_deletion(replaced_by='broadbean.plotting.plotter')
    def plotElement(self):
        pass

    def __eq__(self, other):
        if not isinstance(other, Element):
            return False
        elif not self._data == other._data:
            return False
        elif not self._meta == other._meta:
            return False
        else:
            return True


def _subelementBuilder(blueprint: BluePrint, SR: int,
                       durs: List[float]) -> Dict[str, np.ndarray]:
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

    newdurations = np.array(durations)

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
                                       'point(s). There must be at least '
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
    time = np.linspace(0, sum(newdurations), len(output), endpoint=False)
    m1 = np.zeros_like(time)
    m2 = m1.copy()

    # update the 'absolute time' marker list with 'relative time'
    # (segment bound) markers converted to absolute time
    elapsed_times = np.cumsum([0.0] + list(newdurations))

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
            chunk = int(np.round(dur*SR))
            marker[ind:ind+chunk] = 1

    output = np.array(output)  # TODO: Why is this sometimes needed?

    outdict = {'wfm': output, 'm1': m1, 'm2': m2, 'time': time,
               'newdurations': newdurations}

    return outdict


def elementBuilder(blueprints: Union[BluePrint, list],
                   SR: int, durations: List[float],
                   channels: List[int]=None) -> Dict[int,
                                                     Dict[str, np.ndarray]]:
    """
    Forge blueprints into an element

    Args:
        blueprints: A single blueprint or a list of
            blueprints.
        SR: The sample rate (Sa/s)
        durations: List of durations or a list of lists of durations
            if different blueprints have different durations. If a single list
            is given, this list is used for all blueprints.
        channels: A list specifying the channels of the
            blueprints in the list. If None, channels 1, 2, .. are assigned

    Returns:
        Dictionary with channel numbers (ints) as keys and forged
            blueprints as values. A forged blueprint is a dictionary
            with keys 'wfm', 'm1', 'm2', 'm3', etc, 'time', and
            and 'newdurations'.

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
        fulldurations = [durations]*len(blueprints)
        # durations = [durations for _ in range(len(blueprints))]

    if channels is None:
        channels = [ii for ii in range(len(blueprints))]

    bpdurs = zip(blueprints, fulldurations)
    subelems = [_subelementBuilder(bp, SR, dur) for (bp, dur) in bpdurs]

    outdict = dict(zip(channels, subelems))

    return outdict


@marked_for_deletion(replaced_by='broadbean.plotting.plotter')
def bluePrintPlotter(blueprints, fig=None, axs=None):
    pass


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

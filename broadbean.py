# implementing what Filip and Natalie asked for...
#
# In this iteration, we do it in a horribly object-oriented way

import logging
from inspect import signature
from copy import deepcopy
import functools as ft
import numpy as np
import matplotlib.pyplot as plt
plt.ion()

log = logging.getLogger(__name__)


class ElementDurationError(Exception):
    pass


class SequenceConsistencyError(Exception):
    pass


class PulseAtoms:
    """
    A class full of static methods.
    The basic pulse shapes.

    Any pulse shape function should return a list or an np.array
    and have SR, duration as its final two arguments.
    """

    @staticmethod
    def sine(freq, ampl, off, SR, dur):
        time = np.linspace(0, dur, int(dur*SR))
        freq *= 2*np.pi
        return (ampl*np.sin(freq*time)+off)

    @staticmethod
    def ramp(start, stop, SR, dur):
        slope = (stop-start)/dur
        time = np.linspace(0, dur, int(dur*SR))
        return (slope*time+start)

    @staticmethod
    def waituntil(dummy, SR, dur):
        # for internal call signature consistency, a dummy variable is needed
        return (np.zeros(int(dur*SR)))

    @staticmethod
    def gaussian(ampl, sigma, mu, offset, SR, dur):
        """
        Returns a Gaussian of integral ampl (when offset==0)

        Is by default centred in the middle of the interval
        """
        time = np.linspace(0, dur, int(dur*SR))
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

    def __init__(self, funlist=None, argslist=None, namelist=None, tslist=None,
                 marker1=None, marker2=None, segmentmarker1=None,
                 segmentmarker2=None, SR=None, durations=None):
        """
        Create a BluePrint instance.

        Args:
            funlist (list): List of functions
            argslist (list): List of tuples of arguments
            namelist (list): List of names for the functions
            tslist (list): List of timesteps for each segment
            marker1 (list): List of marker1 specification tuples
            marker2 (list): List of marker2 specifiation tuples

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

        # Are the lists of matching lengths?
        lenlist = [len(funlist), len(argslist), len(namelist)]
        if tslist is not None:
            lenlist.append(len(tslist))
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

        if tslist is None:
            self._tslist = [1]*len(namelist)
        else:
            self._tslist = tslist

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

        if durations is not None:
            self._durslist = []
            steps = [0] + list(np.cumsum(self._tslist))
            for ii in range(len(steps)-1):
                self._durslist.append(tuple(durations[steps[ii]:steps[ii+1]]))
        else:
            self._durslist = None

        self._SR = SR

    @staticmethod
    def _basename(string):
        """
        Remove trailing numbers from a string. (currently removes all numbers)
        """
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
    def length_timesteps(self):
        """
        Returns the number of assigned time steps currently in the blueprint.
        """
        return len(self._tslist)

    @property
    def length_segments(self):
        """
        Returns the number of segments in the blueprint
        """
        return len(self._namelist)

    @property
    def length_seconds(self):
        """
        If possible, returns the length of the blueprint in seconds.
        Returns -1 if insufficient information is specified.
        """
        if (self._SR is None) or (self._durslist is None):
            length_secs = -1
        else:
            # take care of 'waituntils'
            waitinds = [ind for (ind, fun) in enumerate(self._funlist) if
                        fun == 'waituntil']
            durlist = self._durslist[max(waitinds + [0]):]
            durs = [d for dur in self._durslist for d in dur]
            length_secs = self.getLength(self._SR, durs)/self._SR

        return length_secs

    @property
    def length_numpoints(self):
        """
        If possible, returns the length of the blueprint in seconds.
        Returns -1 if insufficient information is specified.
        """
        if (self._SR is None) or (self._durslist is None):
            length_npts = -1
        else:
            durs = [d for dur in self._durslist for d in dur]
            length_npts = self.getLength(self._SR, durs)

        return length_npts

    @property
    def durations(self):
        """
        The flattened list of durations

        (legacy for old API where durations where specified independently)
        """
        durs = [d for dur in self._durslist for d in dur]
        return durs

    @property
    def SR(self):
        """
        Sample rate of the element
        """
        return self._SR

    def showPrint(self):
        """
        Pretty-print the contents of the BluePrint. Not finished.
        """
        # TODO: tidy up this method

        if self._durslist is None:
            dl = [None]*len(self._namelist)
        else:
            dl = self._durslist

        datalists = [self._namelist, self._funlist, self._argslist,
                     self._tslist, dl]

        lzip = zip(*datalists)

        print('Legend: Name, function, arguments, timesteps, durations')

        for ind, (name, fun, args, ts, durs) in enumerate(lzip):
            ind_p = ind+1
            if fun == 'waituntil':
                fun_p = fun
            else:
                fun_p = fun.__str__().split(' ')[1]

            list_p = [ind_p, name, fun_p, args, ts, durs]
            print('Segment {}: "{}", {}, {}, {}, {}'.format(*list_p))
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

        """
        # TODO: is there any reason to use tuples internally?
        # TODO: add input validation

        if replaceeverywhere:
            basename = BluePrint._basename
            name = basename(name)
            nmlst = self._namelist
            replacelist = [nm for nm in nmlst if basename(nm) == name]
        else:
            replacelist = [name]

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
                                     '{}.'.format(sig.parameters))
            if isinstance(arg, int) and arg > len(sig.parameters):
                raise ValueError('No argument {} '.format(arg) +
                                 'of function {}.'.format(function.__name__) +
                                 'Has {} '.format(len(sig.parameters)) +
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
        Change the duration(s) of one or more segments in the blueprint

        Args:
            name (str): The name of the segment in which to change duration
            dur (Union[float, tuple]): The new duration(s). If the segment has
                multiple durations assigned to it, dur must be a tuple. For
                single durations, both a float and a tuple is acceptable.
            replaceeverywhere (Optional[bool]): If True, the duration(s)
                is(are) overwritten in ALL segments where the name matches.
                E.g. 'gaussian1' will match 'gaussian', 'gaussian2',
                etc. If False, only the segment with exact name match
                gets a replacement.

        Raises:
            ValueError: If durations are not specified for the blueprint
            ValueError: If too many or too few durations are given.
            ValueError: If no segment matches the name.
        """

        # Opt-out if blueprint is 'old' style
        if self._durslist is None:
            raise ValueError('Not that kind of blueprint! No durations')

        if replaceeverywhere:
            basename = BluePrint._basename
            name = basename(name)
            nmlst = self._namelist
            replacelist = [nm for nm in nmlst if basename(nm) == name]
        else:
            replacelist = [name]

        for name in replacelist:
            position = self._namelist.index(name)

            # Validation and sanitising
            oldlen = len(self._durslist[position])
            if not isinstance(dur, tuple):
                dur = (dur,)

            if not len(dur) == oldlen:
                raise ValueError('Wrong number of durations! Segment named'
                                 ' {} has '.format(name) +
                                 '{} duration(s).'.format(oldlen) +
                                 ' Received {}.'.format(len(dur)))

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

    def removeSegmentMarker(self, name, markerID):
        """
        Remove a bound marker from a specific segment

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
        position = self._namelist.index(name)
        markerselect[markerID][position] = (0, 0)

    def changeTimeSteps(self, name, n):
        """
        Change the duration (in number of timesteps) of the blueprint segment
        with the specified name.

        Args:
            name (str): The name of a segment of the blueprint.
            n (int): The number of timesteps for this segment to last.
        """
        position = self._namelist.index(name)

        if self._funlist[position] == 'waituntil':
            raise ValueError('Special function waituntil can not last more' +
                             'than one time step')

        n_is_whole_number = float(n).is_integer()
        if not (n >= 1 and n_is_whole_number):
            raise ValueError('n must be a whole number strictly' +
                             ' greater than 0.')

        self._tslist[position] = n

    def copy(self):
        """
        Returns a copy of the BluePrint
        """

        # Needed because of input validation in __init__
        namelist = [self._basename(name) for name in self._namelist.copy()]

        # needed because of __init__'s internal workings
        if self._durslist is not None:
            flatdurlist = [d for dur in self._durslist for d in dur]
        else:
            flatdurlist = None

        return BluePrint(self._funlist.copy(),
                         self._argslist.copy(),
                         namelist,
                         self._tslist.copy(),
                         self.marker1.copy(),
                         self.marker2.copy(),
                         self._segmark1.copy(),
                         self._segmark2.copy(),
                         self._SR,
                         flatdurlist)

    def insertSegment(self, pos, func, args=(), name=None, ts=1, durs=None):
        """
        Insert a segment into the bluePrint.

        Args:
            pos (int): The position at which to add the segment. Counts like
                a python list; 0 is first, -1 is last. Values below -1 are
                not allowed, though.
            func (function): Function describing the segment. Must have its
               duration as the last argument (unless its a special function).
            args (tuple): Tuple of arguments BESIDES duration. Default: ()
            name (str): Name of the segment. If none is given, the segment
                will receive the name of its function, possibly with a number
                appended.
            ts (int): Number of time segments this segment should last.
                Default: 1.
            durs (Optional[Union[float, tuple]]): The duration(s) of the
                segment. Must be a tuple if more than one is specified,
                else both a float and a tuple is acceptable.
        """

        # Validation
        if (durs is not None) and not isinstance(durs, tuple):
            durs = (durs,)
        if isinstance(durs, tuple) and (len(durs) != ts):
            raise ValueError('Inconsistent number of timesteps and'
                             ' durations')

        # Take care of 'waituntil'
        if func == 'waituntil':
            durs = (None,)

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

        # Unfortunate side effect of having durations non-mandatory
        if (durs is not None) and (self._durslist is None):
            self._durslist = []

        if pos == -1:
            self._namelist.append(name)
            self._namelist = self._make_names_unique(self._namelist)
            self._funlist.append(func)
            self._argslist.append(args)
            self._tslist.append(ts)
            self._segmark1.append((0, 0))
            self._segmark2.append((0, 0))
            # allow for old-style duration specification
            if self._durslist is not None:
                self._durslist.append(durs)
        else:
            self._namelist.insert(pos, name)
            self._namelist = self._make_names_unique(self._namelist)
            self._funlist.insert(pos, func)
            self._argslist.insert(pos, args)
            self._tslist.insert(pos, ts)
            self._segmark1.insert(pos, (0, 0))
            self._segmark2.insert(pos, (0, 0))
            # allow for old-style duration specifiation
            if self._durslist is not None:
                self._durslist.insert(pos, durs)

    def removeSegment(self, name):
        """
        Remove the specified segment from the blueprint.

        Args:
            name (str): The name of the segment to remove.
        """
        position = self._namelist.index(name)

        del self._funlist[position]
        del self._argslist[position]
        del self._tslist[position]
        del self._namelist[position]
        del self._segmark1[position]
        del self._segmark2[position]
        del self._durslist[position]

    def plot(self, SR=None):
        """
        Plot the blueprint.

        Args:
            SR (Optional[Union[int, None]]): The sample rate. If None, the sample rate
                of the blueprint is used.

        Raises:
            ValueError: If no sample rate is provided as argument nor set for
            the blueprint.
        """

        if self.SR is None:
            raise ValueError('No sample rate specified. Please provide one!')

        # bluePrintPlotter needs a flat list of durations
        flatdurs = [d for dur in self._durslist for d in dur]
        bluePrintPlotter(self, self.SR, flatdurs)

    def _validateDurations(self, durations):
        """
        Checks wether the number of durations matches the number of segments
        and their specified lengths (including 'waituntils')

        Args:
            durations (list): List of durations

        Raises:
            ValueError: If the length of durations does not match the
                blueprint.
        """

        if sum(self._tslist) != len(durations):
            raise ValueError('The specified timesteps do not match the number '
                             'of durations. '
                             '({} and {})'.format(sum(self._tslist),
                                                  len(durations)))

    def getLength(self, SR, durs):
        """
        Calculate the length of the BluePrint, where it to be forged with
        the specified durations.

        Args:
            durs (list): List of durations

        Returns:
            int: The number of points of the element

        Raises:
            ValueError: If the length of durations does not match the
                blueprint.
        """
        durations = durs.copy()

        self._validateDurations(durations)

        no_of_waits = self._funlist.count('waituntil')
        waitpositions = [ii for ii, el in enumerate(self._funlist)
                         if el == 'waituntil']

        # TODO: This is reuse of elementBuilder code... Refactor?

        # Note: the durations here are the flattened list of tuples of
        # durations, therefore we have pos and flatpos

        for nw in range(no_of_waits):
            flatpos = np.cumsum(self._tslist)[waitpositions[nw]]-1
            pos = waitpositions[nw]
            elapsed_time = sum(durations[:flatpos])
            wait_time = self._argslist[pos][0]
            dur = wait_time - elapsed_time
            if dur < 0:
                raise ValueError('Inconsistent timing. Can not wait until ' +
                                 '{} at position {}.'.format(wait_time, pos) +
                                 ' {} elapsed already'.format(elapsed_time))
            else:
                durations[flatpos] = dur

        return(int(sum(durations)*SR))

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
        tl = self._tslist + other._tslist
        m1 = self.marker1 + other.marker1
        m2 = self.marker2 + other.marker2
        sm1 = self._segmark1 + other._segmark1
        sm2 = self._segmark2 + other._segmark2
        dl = self._durslist + other._durslist

        new_bp = BluePrint()

        new_bp._namelist = new_bp._make_names_unique(nl.copy())
        new_bp._funlist = fl.copy()
        new_bp._argslist = al.copy()
        new_bp._tslist = tl.copy()
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
        if not self._tslist == other._tslist:
            return False
        if not self.marker1 == other.marker2:
            return False
        if not self.marker2 == other.marker2:
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

        self._data[channel] = {}
        self._data[channel]['blueprint'] = blueprint

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

        time = np.linspace(0, int(len(array)/SR), len(array))
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
                                       'SRs. Channel, SR: '
                                       '{}, {} s'.format(*errmssglst))

        # Next the total time
        durations = []
        for channel in channels:
            if 'blueprint' in channel.keys():
                durations.append(channel['blueprint'].length_seconds)
            elif 'array' in channel.keys():
                length = len(channel['array'])/channel['SR']
                durations.append(length)

        if not durations.count(durations[0]) == len(durations):
            errmssglst = zip(list(self._data.keys()), durations)
            raise ElementDurationError('Different channels have different '
                                       'durations. Channel, duration: '
                                       '{}, {} s'.format(*errmssglst))

        # Finally the number of points
        npts = []
        for channel in channels:
            if 'blueprint' in channel.keys():
                npts.append(channel['blueprint'].length_numpoints)
            elif 'array' in channel.keys():
                length = len(channel['array'])
                npts.append(length)

        if not npts.count(npts[0]) == len(npts):
            errmssglst = zip(list(self._data.keys()), npts)
            raise ElementDurationError('Different channels have different '
                                       'npts. Channel, npts: '
                                       '{}, {}'.format(*errmssglst))

        # If these three tests pass, we equip the dictionary with convenient
        # info used by Sequence TODO: Currently sequence2
        self._meta['SR'] = SRs[0]
        self._meta['duration'] = durations[0]

    def getArrays(self):
        """
        Return arrays of the element. Heavily used by the Sequence.

        Returns:
            dict: Dictionary with channel numbers (ints) as keys and forged
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

        Args: go figure
        """

        # TODO: docstring and dur(s) validation

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
        durs = [bp.durations for bp in blueprints]

        bluePrintPlotter(blueprints, self.SR, durs)

        # hack the ylabels
        cur_fig = plt.gcf()
        for ii, channel in enumerate(self.channels):
            oldlabel = cur_fig.axes[ii].get_ylabel()
            newlabel = oldlabel.replace('Signal', 'Ch {}'.format(channel))
            cur_fig.axes[ii].set_ylabel(newlabel)


class Sequence:
    """
    New style sequence.
    """

    def __init__(self):
        """
        Not much to see here...
        """

        # the internal data structure, a dict with tuples as keys and values
        # the key is sequence position (int), the value is element (Element)
        self._data = {}

        # Here goes the sequencing info. Key: position, value: list
        # where list = [wait, nrep, jump, goto]
        self._sequencing = {}

        # The dictionary to store AWG settings
        # Keys will include:
        # 'SR', 'channelXampl'
        self._awgspecs = {}

        # The metainfo to be extracted by measurements
        self._meta = {}

    def setSequenceSettings(self, pos, wait, nreps, jump, goto):
        """
        Set the sequence setting for the sequence element at pos.

        Args:
            pos (int): The sequence element (counting from 1)
            wait (int): The wait state specifying whether to wait for a
                trigger. 0: OFF, don't wait, 1: ON, wait.
            nreps (int): Number of repetitions. 0 corresponds to infinite
                repetitions
            jump (int): Jump target, the position of a sequence element
            goto (int): Goto target, the position of a sequence element
        """

        # Validation (some validation 'postponed' and put in checkConsistency)
        if wait not in [0, 1]:
            raise ValueError('Can not set wait to {}.'.format(wait) +
                             ' Must be either 0 or 1.')

        self._sequencing[pos] = [wait, nreps, jump, goto]

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
        keystr = 'channel{}_amplitude'.format(channel)
        self._awgspecs[keystr] = ampl
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

        # Data mutation
        self._data.update({position: element})

    def checkConsistency(self, verbose=False):
        """
        Checks wether the sequence can be built, i.e. wether all elements
        have waveforms on the same channels and of the same length.
        """
        # TODO: Give helpful info if the check fails

        try:
            SR = self._awgspecs['SR']
        except KeyError:
            raise KeyError('No sample rate specified. Can not perform check')

        # First check that all sample rates agree
        # Since all elements are validated on input, the SR exists
        SRs = [elem.SR for elem in self._data.values()]
        if SRs.count(SRs[0]) != len(SRs):
            failmssg = ('checkConsistency failed: inconsistent sample rates.')
            log.info(failmssg)
            if verbose:
                print(failmssg)
            return False

        # Then check that elements use the same channels
        specchans = []
        for elem in self._data.values():
            chans = elem.channels
            specchans.append(chans)
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

        # Now get the dimensions.
        chans = self._data[1].channels  # All element have the same channels

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
                voltageexponent = np.log10(wfm.max())
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

    def outputForAWGFile(self):
        """
        Returns a sliceable object with items matching the call
        signature of the 'make_*_awg_file' functions of the QCoDeS
        AWG5014 driver. One may then construct an awg file as follows
        (assuming that seq is the sequence object):

        package = seq.outputForAWGFile()
        make_awg_file(*package[:], **kwargs)

        The outputForAWGFile applies all specified signal corrections:
          delay of channels
        """
        # TODO: implement corrections

        # Validation
        if not self.checkConsistency():
            raise ValueError('Can not generate output. Something is '
                             'inconsistent. Please run '
                             'checkConsistency(verbose=True) for more details')
        #
        #  CHANGE CODE FROM THIS POINT
        #
        channels = self.element(1).channels  # all elements have ident. chans
        # We copy the data so that the state of the Sequence is left unaltered
        # by outputting for AWG
        data = deepcopy(self._data)
        seqlen = len(data.keys())
        # check if sequencing information is specified for each element
        if not list(self._sequencing.keys()) == list(range(1, seqlen+1)):
            raise ValueError('Can not generate output for .awg file; '
                             'incorrect sequencer information.')

        # Verify physical amplitude and offset specifiations
        for chan in channels:
            ampkey = 'channel{}_amplitude'.format(chan)
            if ampkey not in self._awgspecs.keys():
                raise KeyError('No amplitude specified for channel '
                               '{}. Can not continue.'.format(chan))
            offkey = 'channel{}_offset'.format(chan)
            if offkey not in self._awgspecs.keys():
                raise KeyError('No offset specified for channel '
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
                    blueprint.insertSegment(0, 'waituntil', (delay,),
                                            'waituntil')
                    # add zeros at the end
                    blueprint.insertSegment(-1, PulseAtoms.ramp, (0, 0),
                                            durs=(maxdelay-delay,))
                    # TODO: is the next line even needed?
                    element.addBluePrint(chan, blueprint)

                else:
                    arrays = element[chan]['array']
                    for ii, arr in enumerate(arrays):
                        pre_wait = np.zeros(int(delay/self.SR))
                        post_wait = np.zeros(int((maxdelay-delay)/self.SR))
                        arrays[ii] = np.concatenate((pre_wait, arr, post_wait))

        # Now forge all the elements as specified
        SR = self._awgspecs['SR']
        elements = []  # the forged elements
        for pos in range(1, seqlen+1):
            elements.append(self.element(pos).getArrays())

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
        goto_states = []
        jump_tos = []

        for pos in range(1, seqlen+1):
            for chanind, chan in enumerate(channels):
                waveforms[chanind].append(elements[pos-1][chan][0])
                m1s[chanind].append(elements[pos-1][chan][1])
                m2s[chanind].append(elements[pos-1][chan][2])

            nreps.append(self._sequencing[pos][1])
            trig_waits.append(self._sequencing[pos][0])
            jump_tos.append(self._sequencing[pos][2])
            goto_states.append(self._sequencing[pos][3])

        output = _AWGOutput((waveforms, m1s, m2s, nreps,
                             trig_waits, goto_states,
                             jump_tos), self.channels)

        return output


def _subelementBuilder(blueprint, SR, durs):
    """
    The function building a blueprint, returning a numpy array.

    This is a single-blueprint forger. Multiple blueprints are forged with
    elementBuilder.
    """

    # Important: building the element must NOT modify any of the mutable
    # inputs, therefore all lists are copied
    funlist = blueprint._funlist.copy()
    argslist = blueprint._argslist.copy()
    namelist = blueprint._namelist.copy()
    tslist = blueprint._tslist.copy()
    marker1 = blueprint.marker1.copy()
    marker2 = blueprint.marker2.copy()
    segmark1 = blueprint._segmark1.copy()
    segmark2 = blueprint._segmark2.copy()

    durations = durs.copy()

    no_of_waits = funlist.count('waituntil')

    if sum(tslist) != len(durations):
        print('-'*45)
        print(tslist, durations)

        raise ValueError('The specified timesteps do not match the number ' +
                         'of durations. ({} and {})'.format(sum(tslist),
                                                            len(durations)))

    # handle waituntil by translating it into a normal function
    waitpositions = [ii for ii, el in enumerate(funlist) if el == 'waituntil']

    # Note: the durations here are the flattened list of tuples of
    # durations, therefore we have pos and flatpos

    for nw in range(no_of_waits):
        flatpos = np.cumsum(tslist)[waitpositions[nw]]-1
        pos = waitpositions[nw]
        funlist[pos] = PulseAtoms.waituntil
        elapsed_time = sum(durations[:flatpos])
        wait_time = argslist[pos][0]
        dur = wait_time - elapsed_time
        if dur < 0:
            raise ValueError('Inconsistent timing. Can not wait until ' +
                             '{} at position {}.'.format(wait_time, pos) +
                             ' {} elapsed already'.format(elapsed_time))
        else:
            durations[flatpos] = dur

    # update the durations to accomodate for some segments having
    # timesteps larger than 1
    newdurations = []
    steps = [0] + list(np.cumsum(blueprint._tslist))
    for ii in range(len(steps)-1):
        dur = sum(durations[steps[ii]:steps[ii+1]])
        newdurations.append(dur)

    # The actual forging of the waveform
    parts = [ft.partial(fun, *args) for (fun, args) in zip(funlist, argslist)]
    blocks = [list(p(SR, d)) for (p, d) in zip(parts, newdurations)]
    output = [block for sl in blocks for block in sl]

    # now make the markers
    time = np.linspace(0, sum(newdurations), sum(newdurations)*SR)  # round off
    m1 = np.zeros_like(time)
    m2 = m1.copy()
    dt = time[1] - time[0]
    # update the 'absolute time' marker list with 'relative time'
    # (segment bound) markers converted to absolute time
    elapsed_times = np.cumsum([0] + newdurations)
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
        dict: Dictionary with channel numbers (ints) as keys and forged
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


def bluePrintPlotter(blueprints, SR, durations, fig=None, axs=None):
    """
    Plots a bluePrint or list of blueprints for easy overview.

    Args:
        blueprints (Union[BluePrint, list]): A single BluePrint or a
            list of blueprints to plot.
        SR (int): The sample rate (Sa/s)
        durations (list): Either a list of durations or a list of lists
            of durations in case the blueprints have different durations.
            If only a single list of durations is given, this list is used
            for all blueprints.
        fig (Union[matplotlib.figure.Figure, None]): The figure on which to
            plot. If None is given, a new instance is created.
        axs (Union[list, None]): A list of
            matplotlib.axes._subplots.AxesSubplot to plot onto. If None is
            given, a new list is created.

    TODO: all sorts of validation on lengths of blueprint and the like
    """

    # Allow single blueprint
    if not isinstance(blueprints, list):
        blueprints = [blueprints]
    # Allow a single durations list for all blueprint
    if not isinstance(durations[0], list):
        durations = [durations]*len(blueprints)

    # Validation
    if not len(durations) == len(blueprints):
        raise ValueError('Number of specified blueprints does not match '
                         'number of specified (sets of) durations '
                         '({} and {})'.format(len(blueprints),
                                              len(durations)))

    if fig is None:
        fig = plt.figure()
    N = len(blueprints)

    if axs is None:
        axs = [fig.add_subplot(N, 1, ii+1) for ii in range(N)]

    for ii in range(N):
        ax = axs[ii]
        arrays, newdurs = _subelementBuilder(blueprints[ii], SR, durations[ii])
        wfm = arrays[0, :]
        m1 = arrays[1, :]
        m2 = arrays[2, :]
        time = np.linspace(0, np.sum(newdurs), np.sum(newdurs)*SR)

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
        yt = ax.get_yticks()
        ax.set_yticks(yt[2:-2])
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

    # validation

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
        return sequence

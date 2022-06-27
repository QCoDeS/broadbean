# This file is for defining the blueprint object

import warnings
from inspect import signature
import functools as ft
from typing import List, Dict
import json
import re

import numpy as np

from .broadbean import PulseAtoms


class SegmentDurationError(Exception):
    pass


class BluePrint():
    """
    The class of a waveform to become.
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

        if any(l != lenlist[0] for l in lenlist):
            raise ValueError('All input lists must be of same length. '
                             'Received lengths: {}'.format(lenlist))
        # Are the names valid names?
        for name in namelist:
            if not isinstance(name, str):
                raise ValueError('All segment names must be strings. '
                                f'Received {name}.')
            if name != '' and name[-1].isdigit():
                raise ValueError('Segment names are not allowed to end'
                                f' in a number. {name} is '
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
                    lst[ind] = f"{un}"
                else:
                    lst[ind] = f"{un}{ii+1}"

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
            segkey = f"segment_{sn+1:02d}"
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

    def write_to_json(self, path_to_file: str) -> None:
        """
        Writes blueprint to JSON file

        Args:
            path_to_file: the path to the file to write to ex:
            path_to_file/blueprint.json
        """
        with open(path_to_file, 'w') as fp:
            json.dump(self.description, fp, indent=4)

    @classmethod
    def blueprint_from_description(cls, blue_dict):
        """
        Returns a blueprint from a description given as a dict

        Args:
            blue_dict: a dict in the same form as returned by
            BluePrint.description
        """
        knowfunctions = {
            f"function PulseAtoms.{fun}": getattr(PulseAtoms, fun)
            for fun in dir(PulseAtoms)
            if "__" not in fun
        }
        seg_mar_list = list(blue_dict.keys())
        seg_list = [s for s in seg_mar_list if 'segment' in s]
        bp_sum = cls()
        for i, seg in enumerate(seg_list):
            seg_dict = blue_dict[seg]
            bp_seg = BluePrint()
            if seg_dict['function'] == 'waituntil':
                arguments = blue_dict[seg]['arguments'].values()
                arguments = (list(arguments)[0][0],)
                bp_seg.insertSegment(i, 'waituntil', arguments)
            else:
                arguments = tuple(blue_dict[seg]['arguments'].values())
                bp_seg.insertSegment(i, knowfunctions[seg_dict['function']],
                                     arguments, name=re.sub(r'\d', "", seg_dict['name']), dur=seg_dict['durations'])
            bp_sum = bp_sum + bp_seg
        bp_sum.marker1 = blue_dict['marker1_abs']
        bp_sum.marker2 = blue_dict['marker2_abs']
        listmarker1 = blue_dict['marker1_rel']
        listmarker2 = blue_dict['marker2_rel']
        bp_sum._segmark1 = [tuple(mark) for mark in listmarker1]
        bp_sum._segmark2 = [tuple(mark) for mark in listmarker2]
        return bp_sum

    @classmethod
    def init_from_json(cls, path_to_file: str) -> 'BluePrint':
        """
        Reads blueprint from JSON file

        Args:
            path_to_file: the path to the file to be read ex:
            path_to_file/blueprint.json
            This function is the inverse of write_to_json
            The JSON file needs to be structured as if it was writen
            by the function write_to_json
        """
        with open(path_to_file) as fp:
            data_loaded = json.load(fp)
        return cls.blueprint_from_description(data_loaded)

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
                raise ValueError(
                    "Inconsistent timing. Can not wait until "
                    + f"{wait_time} at position {pos}."
                    + f" {elapsed_time} elapsed already"
                )
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
                raise ValueError(
                    f"No argument {arg} "
                    + f"of function {function.__name__}."
                    + f" Has {user_params} "
                    + "arguments."
                )

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
            raise KeyError(f"No segment called {name} in blueprint.")

        del self._funlist[position]
        del self._argslist[position]
        del self._namelist[position]
        del self._segmark1[position]
        del self._segmark2[position]
        del self._durslist[position]

        self._namelist = self._make_names_unique(self._namelist)

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
            raise ValueError(
                "Inconsistent timing. Can not wait until "
                + f"{wait_time} at position {pos}."
                + f" {elapsed_time} elapsed already"
            )
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

    intdurations = np.zeros(len(newdurations), dtype=int)

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
    wf_length = np.sum(intdurations)
    parts = [ft.partial(fun, *args) for (fun, args) in zip(funlist, argslist)]
    blocks = [p(SR, d) for (p, d) in zip(parts, intdurations)]
    output = np.fromiter((block for sl in blocks for block in sl), float, count=wf_length)

    # now make the markers
    time = np.linspace(0, sum(newdurations), wf_length, endpoint=False)
    m1 = np.zeros_like(time)
    m2 = np.zeros_like(time)

    # update the 'absolute time' marker list with 'relative time'
    # (segment bound) markers converted to absolute time
    elapsed_times = np.cumsum([0.0] + list(newdurations))

    for pos, spec in enumerate(segmark1):
        if spec[1] != 0:
            ontime = elapsed_times[pos] + spec[0]  # spec is (delay, duration)
            marker1.append((ontime, spec[1]))
    for pos, spec in enumerate(segmark2):
        if spec[1] != 0:
            ontime = elapsed_times[pos] + spec[0]  # spec is (delay, duration)
            marker2.append((ontime, spec[1]))
    msettings = [marker1, marker2]
    marks = [m1, m2]
    for marker, setting in zip(marks, msettings):
        for (t, dur) in setting:
            ind = np.abs(time-t).argmin()
            chunk = int(np.round(dur*SR))
            marker[ind:ind+chunk] = 1

    outdict = {'wfm': output, 'm1': m1, 'm2': m2, 'time': time,
               'newdurations': newdurations}

    return outdict

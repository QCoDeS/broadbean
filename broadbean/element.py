# This file contains the Element definition
from __future__ import annotations

import json
from collections.abc import Sequence
from copy import deepcopy
from typing import Dict, List, Union

import numpy as np

from broadbean.blueprint import BluePrint, _subelementBuilder

from .broadbean import PulseAtoms


class ElementDurationError(Exception):
    pass


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

    def addFlags(
        self, channel: Union[str, int], flags: Sequence[Union[str, int]]
    ) -> None:
        """
        Adds flags for the specified channel.
        List of 4 flags, each of which should be 0 or "" for 'No change', 1 or "H" for 'High',
        2 or "L" for 'Low', 3 or "T" for 'Toggle', 4 or "P" for 'Pulse'.
        """
        if not isinstance(flags, Sequence):
            raise ValueError(
                "Flags should be given as a sequence (e.g. a list or a tuple)."
            )

        if len(flags) != 4:
            raise ValueError("There should be 4 flags in the list.")

        for cnt, i in enumerate(flags):
            if i not in [0, 1, 2, 3, 4, "", "H", "L", "T", "P"]:
                raise ValueError(
                    'Invalid flag at index {cnt}. Allowed flags are 0 or "" (No change), '
                    '1 or "H" (High), 2 or "L" (Low), 3 or "T" (Toggle), '
                    '4 or "P" (Pulse).'
                )

        # replace flag aliases with integers
        flag_aliases = {
            "": 0,
            "H": 1,
            "L": 2,
            "T": 3,
            "P": 4,
            0: 0,
            1: 1,
            2: 2,
            3: 3,
            4: 4,
        }
        flags_int = [flag_aliases[x] for x in flags]

        self._data[channel]["flags"] = flags_int

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
                if "flags" in signal.keys():
                    outdict[channel]["flags"] = signal["flags"]
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

            if "flags" in val.keys():
                desc[str(key)]["flags"] = val["flags"]

        return desc

    def write_to_json(self, path_to_file: str) -> None:
        """
        Writes element to JSON file

        Args:
            path_to_file: the path to the file to write to ex:
            path_to_file/element.json
        """
        with open(path_to_file, 'w') as fp:
            json.dump(self.description, fp, indent=4)

    @classmethod
    def element_from_description(cls, element_dict):
        """
        Returns a blueprint from a description given as a dict

        Args:
            element_dict: a dict in the same form as returned by
            Element.description
        """
        channels_list = list(element_dict.keys())
        elem = cls()
        for chan in channels_list:
            bp_sum = BluePrint.blueprint_from_description(element_dict[chan])
            elem.addBluePrint(int(chan), bp_sum)
        return elem

    @classmethod
    def init_from_json(cls, path_to_file: str) -> Element:
        """
        Reads Element from JSON file

        Args:
            path_to_file: the path to the file to be read ex:
            path_to_file/Element.json
            This function is the inverse of write_to_json
            The JSON file needs to be structured as if it was writen
            by the function write_to_json
        """
        with open(path_to_file) as fp:
            data_loaded = json.load(fp)
        return cls.element_from_description(data_loaded)

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

        if "blueprint" not in self._data[channel].keys():
            raise ValueError(f"No blueprint on channel {channel}.")

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

        if "blueprint" not in self._data[channel].keys():
            raise ValueError(f"No blueprint on channel {channel}.")

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

        if not sum(d >= 0 for d in delays) == len(delays):
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

    def __eq__(self, other):
        if not isinstance(other, Element):
            return False
        elif not self._data == other._data:
            return False
        elif not self._meta == other._meta:
            return False
        else:
            return True

# this file defines the sequence object
# along with a few helpers
import warnings
from copy import deepcopy
from typing import Union, Dict, cast, List, Tuple
import logging

import numpy as np
from schema import Schema, Or, Optional
import json

from broadbean.ripasso import applyInverseRCFilter
from broadbean.element import Element  # TODO: change import to element.py
from broadbean.blueprint import BluePrint
from .broadbean import _channelListSorter  # TODO: change import to helpers.py
from .broadbean import PulseAtoms
from .broadbean import _AWGOutput

log = logging.getLogger(__name__)

fs_schema = Schema({int: {'type': Or('subsequence', 'element'),
                          'content': {int: {'data': {Or(str, int): {str: np.ndarray}},
                                            Optional('sequencing'): {Optional(str):
                                                                    int}}},
                          'sequencing': {Optional(str): int}}})


class SequencingError(Exception):
    pass


class SequenceConsistencyError(Exception):
    pass


class InvalidForgedSequenceError(Exception):
    pass


class SequenceCompatibilityError(Exception):
    pass


class SpecificationInconsistencyError(Exception):
    pass


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
        # or subsequence (Sequence)
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

        newdata1 = {key: self.element(key).copy() for key in self._data.keys()}
        newdata2 = {key + N: other.element(key).copy() for key in other._data.keys()}
        newdata1.update(newdata2)

        newseq._data = newdata1

        newsequencing1 = {
            key: self._sequencing[key].copy() for key in self._sequencing.keys()
        }
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

        keystr = f"channel{channel}_amplitude"
        self._awgspecs[keystr] = ampl
        keystr = f"channel{channel}_offset"
        self._awgspecs[keystr] = offset

    def setChannelAmplitude(self, channel: Union[int, str],
                            ampl: float) -> None:
        """
        Assign the physical voltage amplitude of the channel. This is used
        when making output for real instruments.

        Args:
            channel: The channel number
            ampl: The channel peak-to-peak amplitude (V)
        """
        keystr = f"channel{channel}_amplitude"
        self._awgspecs[keystr] = ampl

    def setChannelOffset(self, channel: Union[int, str],
                         offset: float) -> None:
        """
        Assign the physical voltage offset of the channel. This is used
        by some backends when making output for real instruments

        Args:
            channel: The channel number/name
            offset: The channel offset (V)
        """
        keystr = f"channel{channel}_offset"
        self._awgspecs[keystr] = offset

    def setChannelDelay(self, channel: Union[int, str],
                        delay: float) -> None:
        """
        Assign a delay to a channel. This is used when making output for .awg
        files. Use the delay to compensate for cable length differences etc.
        Zeros are prepended to the waveforms to delay them and correspondingly
        appended to non (or less) delayed channels.

        Args:
            channel: The channel number/name
            delay: The required delay (s)

        Raises:
            ValueError: If a non-integer or non-non-negative channel number is
                given.
        """

        self._awgspecs[f"channel{channel}_delay"] = delay

    def setChannelFilterCompensation(self, channel: Union[str, int],
                                     kind: str, order: int=1,
                                     f_cut: float=None,
                                     tau: float=None) -> None:
        """
        Specify a filter to compensate for.

        The specified channel will get a compensation (pre-distorion) to
        compensate for the specified frequency filter. Just to be clear:
        the INVERSE transfer function of the one you specify is applied.
        Only compensation for simple RC-circuit type high pass and low
        pass is supported.

        Args:
            channel: The channel to apply this to.
            kind: Either 'LP' or 'HP'
            order: The order of the filter to compensate for.
                May be negative. Default: 1.
            f_cut: The cut_off frequency (Hz).
            tau): The time constant (s). Note that
                tau = 1/f_cut and that only one of the two can be specified.

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

        keystr = f"channel{channel}_filtercompensation"
        self._awgspecs[keystr] = {
            "kind": kind,
            "order": order,
            "f_cut": f_cut,
            "tau": tau,
        }

    def addElement(self, position: int, element: Element) -> None:
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

    def addSubSequence(self, position: int, subsequence: 'Sequence') -> None:
        """
        Add a subsequence to the sequence. Overwrites anything previously
        assigned to this position. The subsequence can not contain any
        subsequences itself.

        Args:
            position: The sequence position (starting from 1)
            subsequence: The subsequence to add
        """
        if not isinstance(subsequence, Sequence):
            raise ValueError('Subsequence must be a sequence object. '
                             'Received object of type '
                             '{}.'.format(type(subsequence)))

        for elem in subsequence._data.values():
            if isinstance(elem, Sequence):
                raise ValueError('Subsequences can not contain subsequences.')

        if subsequence.SR != self.SR:
            raise ValueError('Subsequence SR does not match (main) sequence SR'
                             '. ({} and {}).'.format(subsequence.SR, self.SR))

        self._data[position] = subsequence.copy()

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
            chans = _channelListSorter(elem.channels)
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
                seqdict = {'Wait trigger': sequencing['twait'],
                           'Repeat': sequencing['nrep'],
                           'jump_input': sequencing['jump_input'],
                           'jump_target': sequencing['jump_target'],
                           'Go to': sequencing['goto']}
                desc[str(pos)]['sequencing'] = seqdict
            except KeyError:
                desc[str(pos)]['sequencing'] = 'Not set'
        desc['awgspecs'] = self._awgspecs
        return desc

    def write_to_json(self, path_to_file: str) -> None:
        """
        Writes sequences to JSON file

        Args:
            path_to_file: the path to the file to write to ex:
            path_to_file/sequense.json
        """
        with open(path_to_file, 'w') as fp:
            json.dump(self.description, fp, indent=4)

    @classmethod
    def sequence_from_description(cls, seq_dict: dict) -> 'Sequence':
        """
        Returns a sequence from a description given as a dict

        Args:
            seq_dict: a dict in the same form as returned by
            Sequence.description
        """

        awgspecs = seq_dict['awgspecs']
        SR = awgspecs['SR']
        elem_list = list(seq_dict.keys())
        new_instance = cls()

        for ele in elem_list[:-1]:
            channels_list = list(seq_dict[ele]['channels'].keys())
            elem = Element()
            for chan in channels_list:
                bp_sum = BluePrint.blueprint_from_description(seq_dict[ele]['channels'][chan])
                bp_sum.setSR(SR)
                elem.addBluePrint(int(chan), bp_sum)
                if "flags" in seq_dict[ele]["channels"][chan]:
                    flags = seq_dict[ele]["channels"][chan]["flags"]
                    elem.addFlags(int(chan), flags)
                ChannelAmplitude = awgspecs[f"channel{chan}_amplitude"]
                new_instance.setChannelAmplitude(
                    int(chan), ChannelAmplitude
                )  # Call signature: channel, amplitude (peak-to-peak)
                ChannelOffset = awgspecs[f"channel{chan}_offset"]
                new_instance.setChannelOffset(int(chan), ChannelOffset)

            new_instance.addElement(int(ele), elem)
            sequencedict = seq_dict[ele]['sequencing']
            new_instance.setSequencingTriggerWait(int(ele), sequencedict['Wait trigger'])
            new_instance.setSequencingNumberOfRepetitions(int(ele), sequencedict['Repeat'])
            new_instance.setSequencingEventInput(int(ele), sequencedict['jump_input'])
            new_instance.setSequencingEventJumpTarget(int(ele), sequencedict['jump_target'])
            new_instance.setSequencingGoto(int(ele), sequencedict['Go to'])
        new_instance.setSR(SR)
        return new_instance


    @classmethod
    def init_from_json(cls, path_to_file: str) -> 'Sequence':
        """
        Reads sequense from JSON file

        Args:
            path_to_file: the path to the file to be read ex:
            path_to_file/sequense.json
            This function is the inverse of write_to_json
            The JSON file needs to be structured as if it was writen
            by the function write_to_json
        """
        new_instance = cls()
        with open(path_to_file) as fp:
            data_loaded = json.load(fp)

        new_instance = Sequence.sequence_from_description(data_loaded)
        return new_instance

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
        Returns a list of the specified channels of the sequence
        """
        if self.checkConsistency():
            return self.element(1).channels
        else:
            raise SequenceConsistencyError('Sequence not consistent. Can not'
                                           ' figure out the channels.')

    @property
    def points(self):
        """
        Returns the number of points of the sequence, disregarding
        sequencing info (like repetitions). Useful for asserting upload
        times, i.e. the size of the built sequence.
        """
        total = 0
        for elem in self._data.values():
            total += elem.points
        return total

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

    @staticmethod
    def _plotSummary(seq: Dict[int, Dict]) -> Dict[int, Dict[str, np.ndarray]]:
        """
        Return a plotting summary of a subsequence.

        Args:
            seq: The 'content' value of a forged sequence where a
                subsequence resides

        Returns:
            A dict that looks like a forged element, but all waveforms
            are just two points, np.array([min, max])
        """

        output = {}

        # we assume correctness, all postions specify the same channels
        chans = seq[1]['data'].keys()

        minmax = dict(zip(chans, [(0, 0)]*len(chans)))

        for element in seq.values():

            arr_dict = element['data']

            for chan in chans:
                wfm = arr_dict[chan]['wfm']
                if wfm.min() < minmax[chan][0]:
                    minmax[chan] = (wfm.min(), minmax[chan][1])
                if wfm.max() > minmax[chan][1]:
                    minmax[chan] = (minmax[chan][0], wfm.max())
                output[chan] = {'wfm': np.array(minmax[chan]),
                                'm1': np.zeros(2),
                                'm2': np.zeros(2),
                                'time': np.linspace(0, 1, 2)}

        return output

    def forge(self, apply_delays: bool=True,
              apply_filters: bool=True,
              includetime: bool=False) -> Dict[int, Dict]:
        """
        Forge the sequence, applying all specified transformations
        (delays and ripasso filter corrections). Copies the data, so
        that the sequence is not modified by forging.

        Args:
            apply_delays: Whether to apply the assigned channel delays
                (if any)
            apply_filters: Whether to apply the assigned channel filters
                (if any)
            includetime: Whether to include the time axis and the segment
                durations (a list) with the arrays. Used for plotting.

        Returns:
            A nested dictionary holding the forged sequence.
        """
        # Validation
        if not self.checkConsistency():
            raise ValueError('Can not generate output. Something is '
                             'inconsistent. Please run '
                             'checkConsistency(verbose=True) for more details')

        output: Dict[int, Dict] = {}
        channels = self.channels
        data = deepcopy(self._data)
        seqlen = len(data.keys())

        # TODO: in this function, we iterate through the sequence three times
        # It is probably worth considering refactoring that into a single
        # iteration, although that may compromise readability

        # Apply channel delays.

        if apply_delays:
            delays = []
            for chan in channels:
                try:
                    delays.append(self._awgspecs[f'channel{chan}_delay'])
                except KeyError:
                    delays.append(0)

            for pos in range(1, seqlen+1):
                if isinstance(data[pos], Sequence):
                    subseq = data[pos]
                    for elem in subseq._data.values():
                        elem._applyDelays(delays)
                elif isinstance(data[pos], Element):
                    data[pos]._applyDelays(delays)

        # forge arrays and form the output dict
        for pos in range(1, seqlen+1):
            output[pos] = {}
            output[pos]['sequencing'] = self._sequencing[pos]
            if isinstance(data[pos], Sequence):
                subseq = data[pos]
                output[pos]['type'] = 'subsequence'
                output[pos]['content'] = {}
                for pos2 in range(1, subseq.length_sequenceelements+1):
                    output[pos]['content'][pos2] = {'data': {},
                                                    'sequencing': {}}
                    elem = subseq.element(pos2)
                    dictdata = elem.getArrays(includetime=includetime)
                    output[pos]['content'][pos2]['data'] = dictdata
                    seqing = subseq._sequencing[pos2]
                    output[pos]['content'][pos2]['sequencing'] = seqing
                    # TODO: update sequencing
            elif isinstance(data[pos], Element):
                elem = data[pos]
                output[pos]['type'] = 'element'
                dictdata = elem.getArrays(includetime=includetime)
                output[pos]['content'] = {1: {'data': dictdata}}

        # apply filter corrections to forged arrays
        if apply_filters:
            for pos1 in range(1, seqlen+1):
                thiselem = output[pos1]['content']
                for pos2 in thiselem.keys():
                    data = thiselem[pos2]['data']
                    for channame in data.keys():
                        keystr = f'channel{channame}_filtercompensation'
                        if keystr in self._awgspecs.keys():
                            kind = self._awgspecs[keystr]['kind']
                            order = self._awgspecs[keystr]['order']
                            f_cut = self._awgspecs[keystr]['f_cut']
                            tau = self._awgspecs[keystr]['tau']
                            if f_cut is None:
                                f_cut = 1/tau
                            prefilter = data[channame]['wfm']
                            postfilter = applyInverseRCFilter(prefilter,
                                                              self.SR,
                                                              kind,
                                                              f_cut, order,
                                                              DCgain=1)
                            (output[pos1]
                                   ['content']
                                   [pos2]
                                   ['data']
                                   [channame]
                                   ['wfm']) = postfilter

        return output

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
            raise ValueError('Can not generate output for file; '
                             'incorrect sequencer information.')

        # Verify physical amplitude specifiations
        for chan in channels:
            ampkey = f"channel{chan}_amplitude"
            if ampkey not in self._awgspecs.keys():
                raise KeyError('No amplitude specified for channel '
                               '{}. Can not continue.'.format(chan))

        # Apply channel delays.
        delays = []
        for chan in channels:
            try:
                delays.append(self._awgspecs[f"channel{chan}_delay"])
            except KeyError:
                delays.append(0)
        maxdelay = max(delays)

        for pos in range(1, seqlen+1):
            for chanind, chan in enumerate(channels):
                element = data[pos]
                delay = delays[chanind]

                if 'blueprint' in element._data[chan].keys():
                    blueprint = element._data[chan]['blueprint']
                    # prevent information about flags to be lost
                    if "flags" in element._data[chan].keys():
                        flags = element._data[chan]["flags"]
                    else:
                        flags = None

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
                    # If not, remove the code updating the flags below
                    # and the one remembering them above
                    element.addBluePrint(chan, blueprint)
                    if flags is not None:
                        element.addFlags(chan, flags)

                else:
                    arrays = element[chan]['array']
                    for name, arr in arrays.items():
                        pre_wait = np.zeros(int(delay/self.SR))
                        post_wait = np.zeros(int((maxdelay-delay)/self.SR))
                        arrays[name] = np.concatenate((pre_wait, arr,
                                                       post_wait))

        # Now forge all the elements as specified
        elements = []  # the forged elements
        for pos in range(1, seqlen+1):
            elements.append(data[pos].getArrays())

        # Now that the numerical arrays exist, we can apply filter compensation
        for chan in channels:
            keystr = f"channel{chan}_filtercompensation"
            if keystr in self._awgspecs.keys():
                kind = self._awgspecs[keystr]['kind']
                order = self._awgspecs[keystr]['order']
                f_cut = self._awgspecs[keystr]['f_cut']
                tau = self._awgspecs[keystr]['tau']
                if f_cut is None:
                    f_cut = 1/tau
                for pos in range(seqlen):
                    prefilter = elements[pos][chan]['wfm']
                    postfilter = applyInverseRCFilter(prefilter,
                                                      self.SR,
                                                      kind, f_cut, order,
                                                      DCgain=1)
                    elements[pos][chan]['wfm'] = postfilter

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
            offkey = f"channel{chan}_offset"
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
            ampl = self._awgspecs[f"channel{chan}_amplitude"]
            amplitudes.append(ampl)
        if len(amplitudes) == 1:
            amplitudes.append(0)

        for pos in range(1, seqlen+1):
            element = elements[pos-1]
            for chan in channels:
                ampl = self._awgspecs[f"channel{chan}_amplitude"]
                wfm = element[chan]["wfm"]
                # check the waveform length
                if len(wfm) < 2400:
                    raise ValueError('Waveform too short on channel '
                                     '{} at step {}; only {} points. '
                                     'The required minimum is 2400 points.'
                                     ''.format(chan, pos, len(wfm)))
                # check whether the waveform voltages can be realised
                if wfm.max() > ampl / 2:
                    raise ValueError(
                        "Waveform voltages exceed channel range "
                        "on channel {}".format(chan)
                        + f" sequence element {pos}."
                        + f" {wfm.max()} > {ampl/2}!"
                    )
                if wfm.min() < -ampl / 2:
                    raise ValueError(
                        "Waveform voltages exceed channel range "
                        "on channel {}".format(chan)
                        + f" sequence element {pos}. "
                        + f"{wfm.min()} < {-ampl/2}!"
                    )
                element[chan]["wfm"] = wfm
            elements[pos - 1] = element

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
                wfm = elements[pos-1][chan]['wfm']
                m1 = elements[pos-1][chan]['m1']
                m2 = elements[pos-1][chan]['m2']
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

    def outputForSEQXFileWithFlags(
        self,
    ) -> Tuple[
        List[int],
        List[int],
        List[int],
        List[int],
        List[int],
        List[List[np.ndarray]],
        List[float],
        str,
        List[List[List[int]]],
    ]:
        """
        Generate a tuple matching the call signature of the QCoDeS
        AWG70000A driver's `makeSEQXFile` function. Same as outputForSEQXFile(),
        but also includes information about the flags.

        Returns:
            A tuple holding (trig_waits, nreps, event_jumps, event_jump_to,
                go_to, wfms, amplitudes, seqname, flags)
        """

        elements = self._prepareForOutputting()
        seqlen = len(elements)
        channels = self.element(1).channels

        # add flags for every element and channel
        all_flags = []
        for chanind, chan in enumerate(channels):
            flags_pos = []
            for pos in range(1, seqlen + 1):
                if "flags" in elements[pos - 1][chan]:
                    flags = elements[pos - 1][chan]["flags"].tolist()
                else:
                    flags = [0, 0, 0, 0]
                flags_pos.append(flags)
            all_flags.append(flags_pos)

        return self.outputForSEQXFile() + (all_flags,)

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
            offkey = f"channel{chan}_offset"
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
                ampl = self._awgspecs[f"channel{chan}_amplitude"]
                off = self._awgspecs[f"channel{chan}_offset"]
                wfm = element[chan]["wfm"]
                # check whether the waveform voltages can be realised
                if wfm.max() > ampl / 2 + off:
                    raise ValueError(
                        "Waveform voltages exceed channel range "
                        "on channel {}".format(chan)
                        + f" sequence element {pos}."
                        + f" {wfm.max()} > {ampl/2+off}!"
                    )
                if wfm.min() < -ampl / 2 + off:
                    raise ValueError(
                        "Waveform voltages exceed channel range "
                        "on channel {}".format(chan)
                        + f" sequence element {pos}. "
                        + f"{wfm.min()} < {-ampl/2+off}!"
                    )
                wfm = rescaler(wfm, ampl, off)
                element[chan]['wfm'] = wfm
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
                waveforms[chanind].append(elements[pos-1][chan]['wfm'])
                m1s[chanind].append(elements[pos-1][chan]['m1'])
                m2s[chanind].append(elements[pos-1][chan]['m2'])

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

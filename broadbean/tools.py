# High-level tool for sequence building and manipulation
#

import numpy as np
import logging

from broadbean.sequence import (Sequence, SequenceConsistencyError)

log = logging.getLogger(__name__)


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

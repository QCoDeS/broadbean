# Test suite for the Sequence Object of the broadband package
#
# Horribly unfinished.
#
# The strategy is the same as for the BluePrint test suite: we cook up some
# sequences and try to break them. If we can't, everything is prolly OK

import pytest
import broadbean as bb
from broadbean import SequenceCompatibilityError, SequenceConsistencyError

ramp = bb.PulseAtoms.ramp
sine = bb.PulseAtoms.sine


@pytest.fixture
def protosequence1():

    SR = 1e9

    th = bb.BluePrint()
    th.insertSegment(0, ramp, args=(0, 0), name='ramp', durs=10e-6)
    th.insertSegment(1, ramp, args=(1, 1), name='ramp', durs=5e-6)
    th.insertSegment(2, ramp, args=(0, 0), name='ramp', durs=10e-6)
    th.setSR(SR)

    wiggle1 = bb.BluePrint()
    wiggle1.insertSegment(0, sine, args=(4e6, 0.5, 0), durs=25e-6)
    wiggle1.setSR(SR)

    wiggle2 = bb.BluePrint()
    wiggle2.insertSegment(0, sine, args=(8e6, 0.5, 0), durs=25e-6)
    wiggle2.setSR(SR)

    elem1 = bb.Element()
    elem1.addBluePrint(1, th)
    elem1.addBluePrint(2, wiggle1)

    elem2 = bb.Element()
    elem2.addBluePrint(1, th)
    elem2.addBluePrint(2, wiggle2)

    seq = bb.Sequence()
    seq.addElement(1, elem1)
    seq.addElement(2, elem2)
    seq.setSR(SR)

    seq.setChannelVoltageRange(1, 2, 0)
    seq.setChannelVoltageRange(2, 2, 0)
    seq.setSequenceSettings(1, 1, 1, 1, 1)
    seq.setSequenceSettings(2, 1, 1, 1, 1)

    return seq


@pytest.fixture
def protosequence2():

    SR = 1e9

    saw = bb.BluePrint()
    saw.insertSegment(0, ramp, args=(0, 100e-3), durs=11e-6)
    saw.insertSegment(1, 'waituntil', args=(25e-6))

    lineandwiggle = bb.BluePrint()
    lineandwiggle.insertSegment(0, 'waituntil', args=(11e-6))
    lineandwiggle.insertSegment(1, sine, args=(10e6, 50e-6, 10e-6), durs=14e-6)

    elem1 = bb.Element()
    elem1.addBluePrint(1, saw)
    elem1.addBluePrint(2, lineandwiggle)

    elem2 = bb.Element()
    elem2.addBluePrint(2, saw)
    elem2.addBluePrint(1, lineandwiggle)

    seq = bb.Sequence()
    seq.setSR(SR)
    seq.addElement(1, elem1)
    seq.addElement(2, elem2)

    seq.setChannelVoltageRange(1, 1.5, 0)
    seq.setChannelVoltageRange(2, 1, 0)
    seq.setSequenceSettings(1, 0, 2, 0, 2)
    seq.setSequenceSettings(2, 1, 1, 0, 1)

    return seq


@pytest.fixture
def badseq_missing_pos():

    SR = 1e9

    saw = bb.BluePrint()
    saw.insertSegment(0, ramp, args=(0, 100e-3), durs=11e-6)
    saw.insertSegment(1, 'waituntil', args=(25e-6))

    lineandwiggle = bb.BluePrint()
    lineandwiggle.insertSegment(0, 'waituntil', args=(11e-6))
    lineandwiggle.insertSegment(1, sine, args=(10e6, 50e-6, 10e-6), durs=14e-6)

    elem1 = bb.Element()
    elem1.addBluePrint(1, saw)
    elem1.addBluePrint(2, lineandwiggle)

    elem2 = bb.Element()
    elem2.addBluePrint(2, saw)
    elem2.addBluePrint(1, lineandwiggle)

    seq = bb.Sequence()
    seq.setSR(SR)
    seq.addElement(1, elem1)
    seq.addElement(3, elem2)  # <--- A gap in the sequence

    seq.setChannelVoltageRange(1, 1.5, 0)
    seq.setChannelVoltageRange(2, 1, 0)
    seq.setSequenceSettings(1, 0, 2, 0, 2)
    seq.setSequenceSettings(2, 1, 1, 0, 1)

    return seq


@pytest.fixture
def squarepulse_baseelem():

    SR = 1e6

    basebp = bb.BluePrint()
    basebp.insertSegment(0, ramp, (0, 0), durs=0.5e-4)
    basebp.insertSegment(1, ramp, (1, 1), durs=1e-4, name='varyme')
    basebp.insertSegment(2, 'waituntil', 5e-4)
    basebp.setSR(SR)

    baseelem = bb.Element()
    baseelem.addBluePrint(1, basebp)

    return baseelem


##################################################
# INIT and dunderdunder part


@pytest.mark.parametrize('attribute', [('_data'), ('_sequencing'),
                                       ('_awgspecs'), ('_meta')])
def test_copy_positively(protosequence1, attribute):
    new_seq = protosequence1.copy()
    attr1 = new_seq.__getattribute__(attribute)
    attr2 = protosequence1.__getattribute__(attribute)
    assert attr1 == attr2


def test_copy_negatively_01(protosequence1):
    new_seq = protosequence1.copy()
    new_seq.setSequenceSettings(1, 0, 1, 1, 1)
    assert new_seq != protosequence1


def test_copy_negatively_02(protosequence1):
    new_seq = protosequence1.copy()
    new_seq.setChannelVoltageRange(1, 1.9, 0)
    assert new_seq != protosequence1


def test_copy_negatively_03(protosequence1):
    new_seq = protosequence1.copy()
    new_seq.element(1).changeArg(2, 'sine', 'freq', 1e6)
    assert new_seq != protosequence1


def test_copy_and_eq(protosequence1):
    new_seq = protosequence1.copy()
    assert new_seq == protosequence1


def test_addition_fail_vrange(protosequence1, protosequence2):
    with pytest.raises(SequenceCompatibilityError):
        protosequence1 + protosequence2


def test_addition_fail_position(protosequence1, badseq_missing_pos):
    with pytest.raises(SequenceConsistencyError):
        protosequence1 + badseq_missing_pos


def test_addition_data(protosequence1, protosequence2):
    protosequence2.setChannelVoltageRange(1, 2, 0)
    protosequence2.setChannelVoltageRange(2, 2, 0)
    newseq = protosequence1 + protosequence2
    expected_data = {1: protosequence1.element(1),
                     2: protosequence1.element(2),
                     3: protosequence2.element(1),
                     4: protosequence2.element(2)}
    assert newseq._data == expected_data


def test_addition_sequencing(protosequence1, protosequence2):
    protosequence2.setChannelVoltageRange(1, 2, 0)
    protosequence2.setChannelVoltageRange(2, 2, 0)

    newseq = protosequence1 + protosequence2
    expected_sequencing = {1: [1, 1, 1, 1],
                           2: [1, 1, 1, 1],
                           3: [0, 2, 0, 2],
                           4: [1, 1, 0, 1]}
    assert newseq._sequencing == expected_sequencing


def test_addition_awgspecs(protosequence1, protosequence2):
    protosequence2.setChannelVoltageRange(1, 2, 0)
    protosequence2.setChannelVoltageRange(2, 2, 0)

    newseq = protosequence1 + protosequence2

    assert newseq._awgspecs == protosequence1._awgspecs


def test_addition_data_with_empty(protosequence1):
    newseq = bb.Sequence()
    newseq._awgspecs = protosequence1._awgspecs

    newseq = newseq + protosequence1

    assert newseq._data == protosequence1._data

##################################################
# AWG settings

@pytest.mark.parametrize('seqinfo', [([-1, 0, 0, 1]),
                                     ([2, 1, 1, 1]),
                                     ([1, -1, 0, 1]),
                                     ([0, 65537, 0, 1]),
                                     ([0, 2.5, 0, 1]),
                                     ([0, 2, 0.5, 1]),
                                     ([0, 2, 3, 1]),
                                     ([0, 1, 0, 0.5]),
                                     ([0, 1, 0, 3]),
                                     ([0, 1, 0, -1])])
def test_sequencing_input_fail(protosequence1, seqinfo):
    with pytest.raises(ValueError):
        protosequence1.setSequenceSettings(1, *seqinfo)


def test_setSR(protosequence1):
    protosequence1.setSR(1.2e9)
    assert protosequence1._awgspecs['SR'] == 1.2e9


##################################################
# Highest level sequence variers

@pytest.mark.parametrize('channels, names, args, iters',
                         [([1], ['varyme'], ['start', 'stop'], [0.9, 1.0, 1.1]),
                          ([1, 1], ['varyme', 'ramp'], ['start', 'start'], [(1,), (1,2)]),
                          ([1], ['varyme'], ['crazyarg'], [0.9, 1.0, 1.1])])
def test_makeVaryingSequence_fail(squarepulse_baseelem, channels, names,
                                  args, iters):
    with pytest.raises(ValueError):
        bb.makeVaryingSequence(squarepulse_baseelem, channels,
                               names, args, iters)


@pytest.mark.parametrize('seqpos, argslist', [(1, [(0, 0), 2*(1,), (5e-4,)]),
                                              (2, [(0, 0), 2*(1.2,), (5e-4,)]),
                                              (3, [(0, 0), 2*(1.3,), (5e-4,)])])
def test_makeVaryingSequence(squarepulse_baseelem, seqpos, argslist):
    channels = [1, 1]
    names = ['varyme', 'varyme']
    args = ['start', 'stop']
    iters = 2*[[1, 1.2, 1.3]]
    sequence = bb.makeVaryingSequence(squarepulse_baseelem, channels,
                                      names, args, iters)
    assert sequence._data[seqpos]._data[1]['blueprint']._argslist == argslist


def test_repeatAndVarySequence_length(protosequence1):
    poss = [1]
    channels = [1]
    names = ['ramp']
    args = ['start']
    iters = [[1, 1.1, 1.2]]

    newseq = bb.repeatAndVarySequence(protosequence1, poss, channels, names,
                                      args, iters)

    expected_l = len(iters[0])*protosequence1.length_sequenceelements

    assert newseq.length_sequenceelements == expected_l


def test_repeatAndVarySequence_awgspecs(protosequence1):
    poss = (1,)
    channels = [1]
    names = ['ramp']
    args = ['stop']
    iters = [[1, 0.9, 0.8]]

    newseq = bb.repeatAndVarySequence(protosequence1, poss, channels, names,
                                      args, iters)

    assert newseq._awgspecs == protosequence1._awgspecs


def test_repeatAndVarySequence_fail_inputlength1(protosequence1):
    poss = (1, 2)
    channels = [1]
    names = ['ramp']
    args = ['start']
    iters = [(1, 0.2, 0.3)]

    with pytest.raises(ValueError):
        bb.repeatAndVarySequence(protosequence1, poss,
                                 channels, names, args, iters)


def test_repeatAndVarySequence_fail_inputlength2(protosequence1):
    poss = (1, 2)
    channels = [1, 1]
    names = ['ramp', 'ramp']
    args = ['start', 'stop']
    iters = [(1, 0.2, 0.3), (1, 0.2)]

    with pytest.raises(ValueError):
        bb.repeatAndVarySequence(protosequence1, poss,
                                 channels, names, args, iters)


def test_repeatAndVarySequence_fail_consistency(protosequence1,
                                                squarepulse_baseelem):

    protosequence1.addElement(5, squarepulse_baseelem)

    print(protosequence1.checkConsistency())

    poss = (1,)
    channels = [1]
    names = ['ramp']
    args = ['start']
    iters = [(1, 0.2, 0.3)]

    with pytest.raises(SequenceConsistencyError):
        bb.repeatAndVarySequence(protosequence1, poss,
                                 channels, names, args, iters)


@pytest.mark.parametrize('pos', [2, 4, 6])
def test_repeatAndVarySequence_same_elements(protosequence1, pos):
    poss = (1,)
    channels = [1]
    names = ['ramp']
    args = ['start']
    iters = [(1, 0.2, 0.3)]

    newseq = bb.repeatAndVarySequence(protosequence1, poss, channels,
                                      names, args, iters)
    assert newseq.element(pos) == protosequence1.element(2)

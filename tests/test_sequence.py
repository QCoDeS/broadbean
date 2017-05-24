# Test suite for the Sequence Object of the broadband package
#
# Horribly unfinished.
#
# The strategy is the same as for the BluePrint test suite: we cook up some
# sequences and try to break them. If we can't, everything is prolly OK

import pytest
import broadbean as bb

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

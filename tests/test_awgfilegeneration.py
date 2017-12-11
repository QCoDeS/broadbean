# a small test that our output at least matches the signature it should match
# before we make broadbean depend on QCoDeS, we can't directly test
# that a valid .awg file is actually generated

import pytest

import broadbean as bb

ramp = bb.PulseAtoms.ramp
sine = bb.PulseAtoms.sine


@pytest.fixture
def protosequence1():

    SR = 1e9

    th = bb.BluePrint()
    th.insertSegment(0, ramp, args=(0, 0), name='ramp', dur=10e-6)
    th.insertSegment(1, ramp, args=(1, 1), name='ramp', dur=5e-6)
    th.insertSegment(2, ramp, args=(0, 0), name='ramp', dur=10e-6)
    th.setSR(SR)

    wiggle1 = bb.BluePrint()
    wiggle1.insertSegment(0, sine, args=(4e6, 0.5, 0), dur=25e-6)
    wiggle1.setSR(SR)

    wiggle2 = bb.BluePrint()
    wiggle2.insertSegment(0, sine, args=(8e6, 0.5, 0), dur=25e-6)
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
    seq.name = 'protoSequence'

    seq.setChannelVoltageRange(1, 2, 0)
    seq.setChannelVoltageRange(2, 2, 0)
    seq.setSequenceSettings(1, 1, 1, 1, 1)
    seq.setSequenceSettings(2, 1, 1, 1, 1)

    return seq


def test_awg_output(protosequence1):

    # basic check: no exceptions should be raised
    package = protosequence1.outputForAWGFile()

    tst = package[1]

    assert isinstance(tst, tuple)
    assert len(tst) == 7

# a small test that our output at least matches the signature it should match
# before we make broadbean depend on QCoDeS, we can't directly test
# that a valid .awg file is actually generated

import pytest
from hypothesis import HealthCheck, given, settings
import hypothesis.strategies as hst

import broadbean as bb
from broadbean.sequence import Sequence, SequencingError

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
    wiggle1.insertSegment(0, sine, args=(4e6, 0.5, 0, 0), dur=25e-6)
    wiggle1.setSR(SR)

    wiggle2 = bb.BluePrint()
    wiggle2.insertSegment(0, sine, args=(8e6, 0.5, 0, 0), dur=25e-6)
    wiggle2.setSR(SR)

    elem1 = bb.Element()
    elem1.addBluePrint(1, th)
    elem1.addBluePrint(2, wiggle1)

    elem2 = bb.Element()
    elem2.addBluePrint(1, th)
    elem2.addBluePrint(2, wiggle2)

    seq = Sequence()
    seq.addElement(1, elem1)
    seq.addElement(2, elem2)
    seq.setSR(SR)
    seq.name = 'protoSequence'

    seq.setChannelAmplitude(1, 2)
    seq.setChannelAmplitude(2, 2)
    seq.setChannelOffset(1, 0)
    seq.setChannelOffset(2, 0)
    seq.setSequencingTriggerWait(1, 1)
    seq.setSequencingTriggerWait(2, 1)
    seq.setSequencingEventJumpTarget(1, 1)
    seq.setSequencingEventJumpTarget(2, 1)
    seq.setSequencingGoto(1, 1)
    seq.setSequencingGoto(2, 1)

    return seq


def test_awg_output(protosequence1):

    # basic check: no exceptions should be raised
    package = protosequence1.outputForAWGFile()

    tst = package[1]

    assert isinstance(tst, tuple)
    assert len(tst) == 7


def should_raise_sequencingerror(wait, nrep, jump_to, goto, num_elms):
    """
    Function to tell us whether a SequencingError should be raised
    """
    if wait not in [0, 1]:
        return True
    if nrep not in range(0, 16384):
        return True
    if jump_to not in range(-1, num_elms+1):
        return True
    if goto not in range(0, num_elms+1):
        return True
    return False


@settings(max_examples=25, suppress_health_check=(HealthCheck.function_scoped_fixture,))
@given(wait=hst.integers(), nrep=hst.integers(), jump_to=hst.integers(),
       goto=hst.integers())
def test_awg_output_validations(protosequence1, wait, nrep, jump_to, goto):

    protosequence1.setSequencingTriggerWait(1, wait)
    protosequence1.setSequencingNumberOfRepetitions(1, nrep)
    protosequence1.setSequencingEventJumpTarget(1, jump_to)
    protosequence1.setSequencingGoto(1, goto)

    N = protosequence1.length_sequenceelements

    if should_raise_sequencingerror(wait, nrep, jump_to, goto, N):
        with pytest.raises(SequencingError):
            protosequence1.outputForAWGFile()
    else:
        protosequence1.outputForAWGFile()

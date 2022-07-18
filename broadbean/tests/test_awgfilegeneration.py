# a small test that our output at least matches the signature it should match
# before we make broadbean depend on QCoDeS, we can't directly test
# that a valid .awg file is actually generated

import pytest
from hypothesis import HealthCheck, given, settings
import hypothesis.strategies as hst

import broadbean as bb
from broadbean.sequence import PulseSequence, SequencingError

ramp = bb.PulseAtoms.ramp
sine = bb.PulseAtoms.sine


@pytest.fixture
def protosequence1():

    SR = 1e9

    th = bb.BluePrint()
    th.insert_segment(0, ramp, args=(0, 0), name="ramp", dur=10e-6)
    th.insert_segment(1, ramp, args=(1, 1), name="ramp", dur=5e-6)
    th.insert_segment(2, ramp, args=(0, 0), name="ramp", dur=10e-6)
    th.set_sample_rate(SR)

    wiggle1 = bb.BluePrint()
    wiggle1.insert_segment(0, sine, args=(4e6, 0.5, 0, 0), dur=25e-6)
    wiggle1.set_sample_rate(SR)

    wiggle2 = bb.BluePrint()
    wiggle2.insert_segment(0, sine, args=(8e6, 0.5, 0, 0), dur=25e-6)
    wiggle2.set_sample_rate(SR)

    elem1 = bb.Element()
    elem1.add_blueprint(1, th)
    elem1.add_blueprint(2, wiggle1)

    elem2 = bb.Element()
    elem2.add_blueprint(1, th)
    elem2.add_blueprint(2, wiggle2)

    seq = PulseSequence()
    seq.add_element(1, elem1)
    seq.add_element(2, elem2)
    seq.set_sample_rate(SR)
    seq.name = 'protoSequence'

    seq.set_channel_amplitude(1, 2)
    seq.set_channel_amplitude(2, 2)
    seq.set_channel_offset(1, 0)
    seq.set_channel_offset(2, 0)
    seq.set_sequencing_trigger_wait(1, 1)
    seq.set_sequencing_trigger_wait(2, 1)
    seq.set_sequencing_event_jump_target(1, 1)
    seq.set_sequencing_event_jump_target(2, 1)
    seq.set_sequencing_goto(1, 1)
    seq.set_sequencing_goto(2, 1)

    return seq


def test_awg_output(protosequence1):

    # basic check: no exceptions should be raised
    package = protosequence1.output_for_awg_file()

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

    protosequence1.set_sequencing_trigger_wait(1, wait)
    protosequence1.set_sequencing_number_of_repetitions(1, nrep)
    protosequence1.set_sequencing_event_jump_target(1, jump_to)
    protosequence1.set_sequencing_goto(1, goto)

    N = protosequence1.length_sequenceelements

    if should_raise_sequencingerror(wait, nrep, jump_to, goto, N):
        with pytest.raises(SequencingError):
            protosequence1.output_for_awg_file()
    else:
        protosequence1.output_for_awg_file()

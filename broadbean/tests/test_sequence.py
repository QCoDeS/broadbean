# Test suite for the Sequence Object of the broadband package
#
# Horribly unfinished.
#
# The strategy is the same as for the BluePrint test suite: we cook up some
# sequences and try to break them. If we can't, everything is prolly OK

import os

import pytest

import broadbean as bb
from broadbean.sequence import (
    PulseSequence,
    SequenceCompatibilityError,
    SequenceConsistencyError,
)
from broadbean.tools import make_varying_sequence, repeat_and_vary_sequence

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
    wiggle1.insert_segment(0, sine, args=(4e6, 0.5, 0), dur=25e-6)
    wiggle1.set_sample_rate(SR)

    wiggle2 = bb.BluePrint()
    wiggle2.insert_segment(0, sine, args=(8e6, 0.5, 0), dur=25e-6)
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

    seq.set_channel_amplitude(1, 2)
    seq.set_channel_offset(1, 0)
    seq.set_channel_amplitude(2, 2)
    seq.set_channel_offset(2, 0)
    seq.set_sequencing_trigger_wait(1, 1)
    seq.set_sequencing_event_jump_target(1, 1)
    seq.set_sequencing_goto(1, 1)
    seq.set_sequencing_trigger_wait(2, 1)
    seq.set_sequencing_event_jump_target(2, 1)
    seq.set_sequencing_goto(2, 1)

    return seq


@pytest.fixture
def protosequence2():

    SR = 1e9

    saw = bb.BluePrint()
    saw.insert_segment(0, ramp, args=(0, 100e-3), dur=11e-6)
    saw.insert_segment(1, "waituntil", args=(25e-6))
    saw.set_sample_rate(SR)

    lineandwiggle = bb.BluePrint()
    lineandwiggle.insert_segment(0, "waituntil", args=(11e-6))
    lineandwiggle.insert_segment(1, sine, args=(10e6, 50e-6, 10e-6), dur=14e-6)
    lineandwiggle.set_sample_rate(SR)

    elem1 = bb.Element()
    elem1.add_blueprint(1, saw)
    elem1.add_blueprint(2, lineandwiggle)

    elem2 = bb.Element()
    elem2.add_blueprint(2, saw)
    elem2.add_blueprint(1, lineandwiggle)

    seq = PulseSequence()
    seq.set_sample_rate(SR)
    seq.add_element(1, elem1)
    seq.add_element(2, elem2)

    seq.set_channel_amplitude(1, 1.5)
    seq.set_channel_offset(1, 0)
    seq.set_channel_amplitude(2, 1)
    seq.set_channel_offset(2, 0)
    seq.set_sequencing_trigger_wait(1, 0)
    seq.set_sequencing_trigger_wait(2, 1)
    seq.set_sequencing_number_of_repetitions(1, 2)
    seq.set_sequencing_event_jump_target(1, 0)
    seq.set_sequencing_event_jump_target(2, 0)
    seq.set_sequencing_goto(1, 2)
    seq.set_sequencing_goto(2, 1)

    return seq


@pytest.fixture
def badseq_missing_pos():

    SR = 1e9

    saw = bb.BluePrint()
    saw.insert_segment(0, ramp, args=(0, 100e-3), dur=11e-6)
    saw.insert_segment(1, "waituntil", args=(25e-6))
    saw.set_sample_rate(SR)

    lineandwiggle = bb.BluePrint()
    lineandwiggle.insert_segment(0, "waituntil", args=(11e-6))
    lineandwiggle.insert_segment(1, sine, args=(10e6, 50e-6, 10e-6), dur=14e-6)
    lineandwiggle.set_sample_rate(SR)

    elem1 = bb.Element()
    elem1.add_blueprint(1, saw)
    elem1.add_blueprint(2, lineandwiggle)

    elem2 = bb.Element()
    elem2.add_blueprint(2, saw)
    elem2.add_blueprint(1, lineandwiggle)

    seq = PulseSequence()
    seq.set_sample_rate(SR)
    seq.add_element(1, elem1)
    seq.add_element(3, elem2)  # <--- A gap in the sequence

    seq.set_channel_amplitude(1, 1.5)
    seq.set_channel_offset(1, 0)
    seq.set_channel_amplitude(2, 1)
    seq.set_channel_offset(2, 0)
    seq.set_sequencing_trigger_wait(3, 1)
    seq.set_sequencing_number_of_repetitions(1, 2)
    seq.set_sequencing_goto(1, 2)
    seq.set_sequencing_goto(3, 1)


    return seq


@pytest.fixture
def squarepulse_baseelem():

    SR = 1e6

    basebp = bb.BluePrint()
    basebp.insert_segment(0, ramp, (0, 0), dur=0.5e-4)
    basebp.insert_segment(1, ramp, (1, 1), dur=1e-4, name="varyme")
    basebp.insert_segment(2, "waituntil", 5e-4)
    basebp.set_sample_rate(SR)

    baseelem = bb.Element()
    baseelem.add_blueprint(1, basebp)

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
    new_seq.set_sequencing_trigger_wait(1, 0)
    new_seq.set_sequencing_number_of_repetitions(1, 1)
    new_seq.set_sequencing_event_jump_target(1, 1)
    new_seq.set_sequencing_goto(1, 1)

    assert new_seq != protosequence1


def test_copy_negatively_02(protosequence1):
    new_seq = protosequence1.copy()
    new_seq.set_channel_amplitude(1, 1.9)
    assert new_seq != protosequence1


def test_copy_negatively_03(protosequence1):
    new_seq = protosequence1.copy()
    new_seq.element(1).change_blueprint_argument(2, "sine", "freq", 1e6)
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
    protosequence2.set_channel_amplitude(1, 2)
    protosequence2.set_channel_offset(1, 0)
    protosequence2.set_channel_amplitude(2, 2)
    protosequence2.set_channel_offset(2, 0)
    newseq = protosequence1 + protosequence2
    expected_data = {1: protosequence1.element(1),
                     2: protosequence1.element(2),
                     3: protosequence2.element(1),
                     4: protosequence2.element(2)}
    assert newseq._data == expected_data


def test_addition_sequencing1(protosequence1, protosequence2):
    protosequence2.set_channel_amplitude(1, 2)
    protosequence2.set_channel_offset(1, 0)
    protosequence2.set_channel_amplitude(2, 2)
    protosequence2.set_channel_offset(2, 0)

    newseq = protosequence1 + protosequence2
    expected_sequencing = {1: {'twait': 1, 'nrep': 1, 'jump_target': 1,
                               'goto': 1, 'jump_input': 0},
                           2: {'twait': 1, 'nrep': 1, 'jump_target': 1,
                               'goto': 1, 'jump_input': 0},
                           3: {'twait': 0, 'nrep': 2, 'jump_target': 0,
                               'goto': 4, 'jump_input': 0},
                           4: {'twait': 1, 'nrep': 1, 'jump_target': 0,
                               'goto': 3, 'jump_input': 0}}
    assert newseq._sequencing == expected_sequencing


def test_addition_sequencing2(protosequence1, protosequence2):
    protosequence2.set_channel_amplitude(1, 2)
    protosequence2.set_channel_offset(1, 0)
    protosequence2.set_channel_amplitude(2, 2)
    protosequence2.set_channel_offset(2, 0)

    newseq = protosequence2 + protosequence1
    expected_sequencing = {3: {'twait': 1, 'nrep': 1, 'jump_target': 3,
                               'goto': 3, 'jump_input': 0},
                           4: {'twait': 1, 'nrep': 1, 'jump_target': 3,
                               'goto': 3, 'jump_input': 0},
                           1: {'twait': 0, 'nrep': 2, 'jump_target': 0,
                               'goto': 2, 'jump_input': 0},
                           2: {'twait': 1, 'nrep': 1, 'jump_target': 0,
                               'goto': 1, 'jump_input': 0}}
    assert newseq._sequencing == expected_sequencing


def test_addition_awgspecs(protosequence1, protosequence2):
    protosequence2.set_channel_amplitude(1, 2)
    protosequence2.set_channel_offset(1, 0)
    protosequence2.set_channel_amplitude(2, 2)
    protosequence2.set_channel_offset(2, 0)

    newseq = protosequence1 + protosequence2

    assert newseq._awgspecs == protosequence1._awgspecs


def test_addition_data_with_empty(protosequence1):
    newseq = PulseSequence()
    newseq._awgspecs = protosequence1._awgspecs

    newseq = newseq + protosequence1

    assert newseq._data == protosequence1._data


def test_add_subsequence_raises(protosequence1, squarepulse_baseelem):

    # raise if a non-Sequence object is added
    with pytest.raises(ValueError):
        protosequence1.add_subsequence(1, squarepulse_baseelem)

    seq = PulseSequence()
    seq.add_element(1, squarepulse_baseelem)
    seq.set_sample_rate(squarepulse_baseelem.sample_rate)

    mainseq = PulseSequence()
    mainseq.set_sample_rate(seq.sample_rate / 2)

    # raise if the subsequence sample rate does not match the main seq. SR
    with pytest.raises(ValueError):
        mainseq.add_subsequence(1, seq)

    mainseq.set_sample_rate(seq.sample_rate)
    mainseq.add_subsequence(1, seq)

    doublemainseq = PulseSequence()
    doublemainseq.set_sample_rate(seq.sample_rate)

    with pytest.raises(ValueError):
        doublemainseq.add_subsequence(1, mainseq)

##################################################
# AWG settings


def test_set_sample_rate(protosequence1):
    protosequence1.set_sample_rate(1.2e9)
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
        make_varying_sequence(squarepulse_baseelem, channels, names, args, iters)


@pytest.mark.parametrize('seqpos, argslist', [(1, [(0, 0), 2*(1,), (5e-4,)]),
                                              (2, [(0, 0), 2*(1.2,), (5e-4,)]),
                                              (3, [(0, 0), 2*(1.3,), (5e-4,)])])
def test_makeVaryingSequence(squarepulse_baseelem, seqpos, argslist):
    channels = [1, 1]
    names = ["varyme", "varyme"]
    args = ["start", "stop"]
    iters = 2 * [[1, 1.2, 1.3]]
    sequence = make_varying_sequence(squarepulse_baseelem, channels, names, args, iters)
    assert sequence._data[seqpos]._data[1]["blueprint"]._argslist == argslist


def test_repeatAndVarySequence_length(protosequence1):
    poss = [1]
    channels = [1]
    names = ['ramp']
    args = ['start']
    iters = [[1, 1.1, 1.2]]

    newseq = repeat_and_vary_sequence(
        protosequence1, poss, channels, names, args, iters
    )

    expected_l = len(iters[0])*protosequence1.length_sequenceelements

    assert newseq.length_sequenceelements == expected_l


def test_repeatAndVarySequence_awgspecs(protosequence1):
    poss = (1,)
    channels = [1]
    names = ['ramp']
    args = ['stop']
    iters = [[1, 0.9, 0.8]]

    newseq = repeat_and_vary_sequence(
        protosequence1, poss, channels, names, args, iters
    )

    assert newseq._awgspecs == protosequence1._awgspecs


def test_repeatAndVarySequence_fail_inputlength1(protosequence1):
    poss = (1, 2)
    channels = [1]
    names = ['ramp']
    args = ['start']
    iters = [(1, 0.2, 0.3)]

    with pytest.raises(ValueError):
        repeat_and_vary_sequence(protosequence1, poss, channels, names, args, iters)


def test_repeatAndVarySequence_fail_inputlength2(protosequence1):
    poss = (1, 2)
    channels = [1, 1]
    names = ['ramp', 'ramp']
    args = ['start', 'stop']
    iters = [(1, 0.2, 0.3), (1, 0.2)]

    with pytest.raises(ValueError):
        repeat_and_vary_sequence(protosequence1, poss, channels, names, args, iters)


def test_repeatAndVarySequence_fail_consistency(protosequence1,
                                                squarepulse_baseelem):

    protosequence1.add_element(5, squarepulse_baseelem)

    print(protosequence1.check_consistency())

    poss = (1,)
    channels = [1]
    names = ['ramp']
    args = ['start']
    iters = [(1, 0.2, 0.3)]

    with pytest.raises(SequenceConsistencyError):
        repeat_and_vary_sequence(protosequence1, poss, channels, names, args, iters)


@pytest.mark.parametrize('pos', [2, 4, 6])
def test_repeatAndVarySequence_same_elements(protosequence1, pos):
    poss = (1,)
    channels = [1]
    names = ['ramp']
    args = ['start']
    iters = [(1, 0.2, 0.3)]

    newseq = repeat_and_vary_sequence(
        protosequence1, poss, channels, names, args, iters
    )
    assert newseq.element(pos) == protosequence1.element(2)


def test_write_read_sequence(protosequence1, protosequence2, tmp_path):
    d = tmp_path / "Sequence"
    d.mkdir()
    for seq in (protosequence1, protosequence2):
        seq.write_to_json(os.path.join(d, "Seq.json"))
        readbackseq = PulseSequence.init_from_json(os.path.join(d, "Seq.json"))
        assert seq == readbackseq

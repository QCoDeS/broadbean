# This test suite is meant to test everything related to forging, i.e. making
# numpy arrays out of BluePrints

from hypothesis import given
import hypothesis.strategies as hst
import pytest
import numpy as np

import broadbean as bb
from broadbean.blueprint import _subelementBuilder, SegmentDurationError
from broadbean.ripasso import applyInverseRCFilter
from broadbean.sequence import Sequence

import matplotlib.pyplot as plt
plt.ion()

ramp = bb.PulseAtoms.ramp
sine = bb.PulseAtoms.sine


@pytest.fixture
def sequence_maker():
    """
    Return a function returning a sequence with some top hat pulses
    """

    def make_seq(seqlen, channels, SR):

        seq = Sequence()
        seq.setSR(SR)

        for pos in range(1, seqlen+1):

            elem = bb.Element()

            for chan in channels:
                bp = bb.BluePrint()
                bp.insertSegment(-1, ramp, (0, 0), dur=20/SR)
                bp.insertSegment(-1, ramp, (1, 1), dur=10/SR)
                bp.insertSegment(-1, ramp, (0, 0), dur=5/SR)
                bp.setSR(SR)
                elem.addBluePrint(chan, bp)

            seq.addElement(pos, elem)

        return seq

    return make_seq


def _has_period(array: np.ndarray, period: int) -> bool:
    """
    Check whether an array has a specific period
    """
    try:
        array = array.reshape((len(array)//period, period))
    except ValueError:
        return False

    for n in range(period):
        column = array[:, n]
        if not np.allclose(column, column[0]):
            return False

    return True


@given(SR=hst.integers(min_value=100, max_value=50*10**9),
       ratio=hst.floats(min_value=1e-6, max_value=10))
def test_too_short_durations_rejected(SR, ratio):

    # Any ratio larger than 1 will be rounded up by
    # _subelementBuilder to yield two points
    # (is that desired?)
    shortdur = ratio*1/SR
    # however, since this is caluclated as dur*SR
    # it is possible for ratio > 1.5 but
    # shortdur*SR to be smaller due to fp roundoff
    # here we explicitly use shortdur*SR for that reason
    round_tripped_ratio = shortdur*SR

    bp = bb.BluePrint()
    bp.setSR(SR)
    bp.insertSegment(0, ramp, (0, 1), dur=shortdur)

    if round_tripped_ratio < 1.5:
        with pytest.raises(SegmentDurationError):
            _subelementBuilder(bp, SR, [shortdur])
    else:
        _subelementBuilder(bp, SR, [shortdur])


def test_correct_periods():

    SR = 1e9
    dur = 100e-9
    freqs = [100e6, 200e6, 500e6]
    periods = [int(SR/freq) for freq in freqs]

    for freq, period in zip(freqs, periods):
        bp = bb.BluePrint()
        bp.insertSegment(0, sine, (freq, 1, 0, 0), dur=dur)
        bp.setSR(SR)

        wfm = _subelementBuilder(bp, SR, [dur])['wfm']

        assert _has_period(wfm, period)


def test_correct_marker_times():

    SR = 100

    bp = bb.BluePrint()
    bp.insertSegment(-1, ramp, (0, 0), dur=1, name='A')
    bp.insertSegment(-1, ramp, (0, 0), dur=1, name='B')
    bp.insertSegment(-1, ramp, (0, 0), dur=1, name='C')
    bp.setSR(SR)

    bp.setSegmentMarker('A', (0, 0.5), 1)
    bp.setSegmentMarker('B', (-0.1, 0.25), 2)
    bp.setSegmentMarker('C', (0.1, 0.25), 1)

    forged_bp = _subelementBuilder(bp, SR, [1, 1, 1])

    m1 = forged_bp['m1']

    assert (m1 == np.concatenate((np.ones(50), np.zeros(160),
                                  np.ones(25), np.zeros(65)))).all()


def test_apply_filters_in_forging(sequence_maker):
    """
    Assign some filters, forge and assert that they were applied
    """
    N = 5
    channels = [1, 2, 'my_channel']
    filter_orders = [1, 2, 3]
    SR = 1e9

    seq = sequence_maker(N, channels, SR)

    for chan, order in zip(channels, filter_orders):
        seq.setChannelFilterCompensation(chan, kind='HP',
                                         order=order, f_cut=SR/10,
                                         tau=None)

    forged_seq_bare = seq.forge(apply_filters=False)
    forged_seq_filtered = seq.forge(apply_filters=True)

    for chan, order in zip(channels, filter_orders):

        wfm_bare = forged_seq_bare[1]['content'][1]['data'][chan]['wfm']
        expected = applyInverseRCFilter(wfm_bare, SR, kind='HP',
                                        f_cut=SR/10, order=order, DCgain=1)

        forged = forged_seq_filtered[1]['content'][1]['data'][chan]['wfm']

        assert np.all(expected == forged)

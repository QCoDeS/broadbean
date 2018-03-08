# This test suite is meant to test everything related to forging, i.e. making
# numpy arrays out of BluePrints

from hypothesis import given
import hypothesis.strategies as hst
import pytest
import numpy as np

import broadbean as bb
from broadbean.broadbean import _subelementBuilder
from broadbean import SegmentDurationError

ramp = bb.PulseAtoms.ramp
sine = bb.PulseAtoms.sine


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


@given(SR=hst.integers(min_value=100, max_value=50e9),
       ratio=hst.floats(min_value=1e-6, max_value=10))
def test_too_short_durations_rejected(SR, ratio):

    # Any ratio larger than 1 will be rounded up by
    # _subelementBuilder to yield two points
    # (is that desired?)
    shortdur = ratio*1/SR

    bp = bb.BluePrint()
    bp.setSR(SR)
    bp.insertSegment(0, ramp, (0, 1), dur=shortdur)

    if ratio < 1.5:
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

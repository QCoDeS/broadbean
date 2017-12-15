# This test suite is meant to test everything related to forging, i.e. making
# numpy arrays out of BluePrints

from hypothesis import given
import hypothesis.strategies as hst
import pytest
import broadbean as bb
from broadbean.broadbean import _subelementBuilder
from broadbean import SegmentDurationError

ramp = bb.PulseAtoms.ramp
sine = bb.PulseAtoms.sine


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

    if ratio <= 1:
        with pytest.raises(SegmentDurationError):
            _subelementBuilder(bp, SR, [shortdur])
    else:
        _subelementBuilder(bp, SR, [shortdur])

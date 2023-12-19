# Test suite for the Ripasso module of the broadband package

import numpy as np
import pytest

import broadbean as bb
from broadbean.ripasso import applyInverseRCFilter, applyRCFilter

NUM_POINTS = 2500


@pytest.fixture
def squarewave():
    periods = 5
    periods = int(periods)
    array = np.zeros(NUM_POINTS)

    for n in range(periods):
        array[
            int(n * NUM_POINTS / periods) : int((2 * n + 1) * NUM_POINTS / 2 / periods)
        ] = 1

    return array


def test_rc_filter(squarewave):
    # Test RC filter and pre-compensation of filter
    # Check that after filtering and pre-compensation, processed signal differs from the original one by a constant value
    SR = int(10e3)
    for filter_type in ["HP", "LP"]:
        signal1_filtered = applyRCFilter(squarewave, SR, filter_type, f_cut=12, order=1)
        signal1_filtered2 = applyInverseRCFilter(
            signal1_filtered, SR, filter_type, f_cut=12, order=1
        )
        difference = np.abs(np.diff(squarewave - signal1_filtered2))
        assert np.all(np.isclose(difference, 0))


def test_output_seqx_file(squarewave):
    SR = int(10e3)
    elem1 = bb.Element()
    signal1_filtered = applyInverseRCFilter(squarewave, SR, "HP", f_cut=12, order=1)
    elem1.addArray(
        1, signal1_filtered, SR, m1=np.zeros(NUM_POINTS), m2=np.zeros(NUM_POINTS)
    )
    seq1 = bb.Sequence()
    seq1.addElement(1, elem1)
    seq1.setSR(elem1.SR)
    seq1.setChannelAmplitude(1, 2.5)
    seqx_input = seq1.outputForSEQXFile()
    assert np.all(seqx_input[5][0][0][0] == signal1_filtered)

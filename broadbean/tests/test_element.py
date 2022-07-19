# Test suite for the Element Object of the broadband package
#
# We let the test_blueprint.py test the BluePrint and only test that Elements
# work on the Element level

import pytest
import broadbean as bb
import numpy as np
from broadbean.element import ElementDurationError, Element
from hypothesis import HealthCheck, given, settings
import hypothesis.strategies as hst
import os

ramp = bb.PulseAtoms.ramp
sine = bb.PulseAtoms.sine
tophat_SR = 2000


@pytest.fixture(scope='function')
def blueprint_tophat():
    """
    Return a blueprint consisting of three slopeless ramps forming something
    similar to a tophat
    """
    th = bb.BluePrint()
    th.insert_segment(0, ramp, args=(0, 0), name="ramp", dur=1)
    th.insert_segment(1, ramp, args=(1, 1), name="ramp", dur=0.5)
    th.insert_segment(2, ramp, args=(0, 0), name="ramp", dur=1)
    th.set_sample_rate(tophat_SR)

    return th


@pytest.fixture
def mixed_element(blueprint_tophat):
    """
    An element with blueprints and arrays
    """

    noise = np.random.randn(blueprint_tophat.points)
    wiggle = bb.BluePrint()
    wiggle.insert_segment(0, sine, args=(1, 10, 0, 0), dur=2.5)
    wiggle.set_sample_rate(blueprint_tophat.SR)

    elem = Element()
    elem.add_blueprint(1, blueprint_tophat)
    elem.add_array(2, noise, blueprint_tophat.SR)
    elem.add_blueprint(3, wiggle)

    return elem


##################################################
# TEST BARE INITIALISATION


def test_bare_init(blueprint_tophat):
    elem = Element()
    elem.add_blueprint(1, blueprint_tophat)
    assert list(elem._data.keys()) == [1]


def test_equality_true(blueprint_tophat):
    elem1 = Element()
    elem2 = Element()
    elem1.add_blueprint(1, blueprint_tophat)
    elem2.add_blueprint(1, blueprint_tophat)
    assert elem1 == elem2


def test_equality_false(blueprint_tophat):
    elem1 = Element()
    elem2 = Element()
    elem1.add_blueprint(1, blueprint_tophat)
    elem2.add_blueprint(1, blueprint_tophat)
    elem1.change_blueprint_argument(1, "ramp", "start", 2)
    assert elem1 != elem2


def test_copy(blueprint_tophat):
    elem1 = Element()
    elem1.add_blueprint(1, blueprint_tophat)
    elem2 = elem1.copy()
    assert elem1 == elem2

##################################################
# Adding things to the Element goes hand in hand
# with duration validation


def test_addArray():

    SR = 1e9
    N = 2500

    wfm = np.linspace(0, N/SR, N)
    m1 = np.zeros(N)
    m2 = np.ones(N)

    elem = Element()
    elem.add_array(1, wfm, SR, m1=m1, m2=m2)
    elem.add_array("2", wfm, SR, m1=m1)
    elem.add_array("readout_channel", wfm, SR, m2=m2)

    elem.validate_durations()

    M = 2400
    wfm2 = np.linspace(0, M/SR, M)
    elem.add_array(3, wfm2, SR)

    with pytest.raises(ElementDurationError):
        elem.validate_durations()

    with pytest.raises(ValueError):
        elem.add_array(1, wfm, SR, m1=m1[:-1])

    with pytest.raises(ValueError):
        elem.add_array(2, wfm, SR, m2=m2[3:])


@settings(max_examples=25, suppress_health_check=(HealthCheck.function_scoped_fixture,))
@given(SR1=hst.integers(min_value=1,max_value=25*10**8), SR2=hst.integers(min_value = 1,max_value = 25*10**8),
       N=hst.integers(min_value=2,max_value=25*10**6), M=hst.integers(min_value=2,max_value=25*10**6))
def test_invalid_durations(SR1, SR2, N, M):
    """
    There are soooo many ways to have invalid durations, here
    we hit a couple of them
    """

    # differing sample rates

    elem = Element()
    bp = bb.BluePrint()

    bp.insert_segment(0, ramp, (0, 0), dur=N / SR2)
    bp.set_sample_rate(SR2)

    wfm = np.linspace(-1, 1, N)
    elem.add_array(1, wfm, SR1)
    elem.add_blueprint(2, bp)

    if SR1 == SR2:
        elem.validate_durations()
    else:
        with pytest.raises(ElementDurationError):
            elem.validate_durations()

    # differing durations
    bp1 = bb.BluePrint()
    bp1.insert_segment(0, ramp, (0, 1), dur=N / SR1)
    bp1.set_sample_rate(SR1)

    bp2 = bb.BluePrint()
    bp2.insert_segment(0, ramp, (0, 2), dur=M / SR1)
    bp2.set_sample_rate(SR1)

    elem = Element()
    elem.add_blueprint(1, bp1)
    elem.add_blueprint(2, bp2)

    if N == M:
        elem.validate_durations()
    else:
        with pytest.raises(ElementDurationError):
            elem.validate_durations()


def test_apply_delays(mixed_element):

    delays = [1e-1, 0, 0]

    assert mixed_element.duration == 2.5

    arrays_before = mixed_element.get_arrays()
    assert len(arrays_before[1]['wfm']) == 5000

    with pytest.raises(ValueError):
        mixed_element._apply_delays([-0.1, 3, 4])

    with pytest.raises(ValueError):
        mixed_element._apply_delays([0, 1])

    element = mixed_element.copy()
    element._apply_delays(delays)

    arrays_after = element.get_arrays()
    assert len(arrays_after[1]['wfm']) == 5200

    assert mixed_element.duration == 2.5
    assert element.duration == 2.6

    assert element._data[1]['blueprint'].length_segments == 4
    assert element._data[3]['blueprint'].length_segments == 2


##################################################
# Input validation


@pytest.mark.parametrize('improper_bp', [{1: 2}, 'blueprint', bb.BluePrint()])
def test_input_fail1(improper_bp):
    elem = Element()
    with pytest.raises(ValueError):
        elem.add_blueprint(1, improper_bp)

##################################################
# Properties


@settings(max_examples=25, suppress_health_check=(HealthCheck.function_scoped_fixture,))
@given(SR=hst.integers(min_value=1,max_value=25*10**8), N=hst.integers(min_value=2,max_value=25*10**6))
def test_points(SR, N):
    elem = Element()

    with pytest.raises(KeyError):
        elem.points

    bp = bb.BluePrint()

    bp.insert_segment(0, ramp, (0, 0), dur=N / SR)
    bp.set_sample_rate(SR)

    wfm = np.linspace(-1, 1, N)
    elem.add_array(1, wfm, SR)
    elem.add_blueprint(2, bp)

    assert elem.points == N

    elem = Element()
    bp = bb.BluePrint()

    bp.insert_segment(0, ramp, (0, 0), dur=N / SR)
    bp.set_sample_rate(SR)

    wfm = np.linspace(-1, 1, N)
    elem.add_array(2, wfm, SR)
    elem.add_blueprint(1, bp)

    assert elem.points == N


def test_write_read_element(blueprint_tophat, tmp_path):
    elem = Element()
    elem.add_blueprint(1, blueprint_tophat)
    d = tmp_path / "Element"
    d.mkdir()
    elem.write_to_json(os.path.join(d, "ele.json"))
    readback_elem = Element.init_from_json(os.path.join(d, "ele.json"))
    assert elem.description == readback_elem.description

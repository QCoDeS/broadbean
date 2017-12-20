# Test suite for the Element Object of the broadband package
#
# We let the test_blueprint.py test the BluePrint and only test that Elements
# work on the Element level

import pytest
import broadbean as bb
import numpy as np
from broadbean.broadbean import ElementDurationError

ramp = bb.PulseAtoms.ramp
sine = bb.PulseAtoms.sine
tophat_SR = 2000


@pytest.fixture
def blueprint_tophat():
    """
    Return a blueprint consisting of three slopeless ramps forming something
    similar to a tophat
    """
    th = bb.BluePrint()
    th.insertSegment(0, ramp, args=(0, 0), name='ramp', dur=1)
    th.insertSegment(1, ramp, args=(1, 1), name='ramp', dur=0.5)
    th.insertSegment(2, ramp, args=(0, 0), name='ramp', dur=1)
    th.setSR(tophat_SR)

    return th

##################################################
# TEST BARE INITIALISATION


def test_bare_init(blueprint_tophat):
    elem = bb.Element()
    elem.addBluePrint(1, blueprint_tophat)
    assert list(elem._data.keys()) == [1]


def test_equality_true(blueprint_tophat):
    elem1 = bb.Element()
    elem2 = bb.Element()
    elem1.addBluePrint(1, blueprint_tophat)
    elem2.addBluePrint(1, blueprint_tophat)
    assert elem1 == elem2


def test_equality_false(blueprint_tophat):
    elem1 = bb.Element()
    elem2 = bb.Element()
    elem1.addBluePrint(1, blueprint_tophat)
    elem2.addBluePrint(1, blueprint_tophat)
    elem1.changeArg(1, 'ramp', 'start', 2)
    assert elem1 != elem2


def test_copy(blueprint_tophat):
    elem1 = bb.Element()
    elem1.addBluePrint(1, blueprint_tophat)
    elem2 = elem1.copy()
    assert elem1 == elem2

##################################################
# Adding things to the Element


def test_addArray():

    SR = 1e9
    N = 2500

    wfm = np.linspace(0, N/SR, N)
    m1 = np.zeros(N)
    m2 = np.ones(N)

    elem = bb.Element()
    elem.addArray(1, wfm, SR, m1, m2)
    elem.addArray(2, wfm, SR, m1)
    elem.addArray(3, wfm, SR, m2=m2)

    elem.validateDurations()

    M = 2400
    wfm2 = np.linspace(0, M/SR, M)
    elem.addArray(3, wfm2, SR)

    with pytest.raises(ElementDurationError):
        elem.validateDurations()

    with pytest.raises(ValueError):
        elem.addArray(1, wfm, SR, m1[:-1])

    with pytest.raises(ValueError):
        elem.addArray(2, wfm, SR, m2=m2[3:])

##################################################
# Input validation


@pytest.mark.parametrize('improper_bp', [{1: 2}, 'blueprint', bb.BluePrint()])
def test_input_fail1(improper_bp):
    elem = bb.Element()
    with pytest.raises(ValueError):
        elem.addBluePrint(1, improper_bp)

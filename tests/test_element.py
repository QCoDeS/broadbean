# Test suite for the Element Object of the broadband package
#
# We let the test_blueprint.py test the BluePrint and only test that Elements
# work on the Element level

import pytest
import broadbean as bb

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
    th.insertSegment(0, ramp, args=(0, 0), name='ramp', durs=1)
    th.insertSegment(1, ramp, args=(1, 1), name='ramp', durs=0.5)
    th.insertSegment(2, ramp, args=(0, 0), name='ramp', durs=1)
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

# Test suite for everything subsequence related for broadbean
# Sequences

import pytest
import numpy as np

import broadbean as bb
from broadbean.sequence import fs_schema, Sequence

ramp = bb.PulseAtoms.ramp
sine = bb.PulseAtoms.sine
gauss = bb.PulseAtoms.gaussian

SR1 = 1e9

forged_sequence_schema = fs_schema


@pytest.fixture
def subseq1():
    """
    A small sequence meant to be used as a subsequence
    """

    longdur = 201e-9

    wait = bb.BluePrint()
    wait.insertSegment(0, ramp, args=(0, 0), dur=10e-9)
    wait.setSR(SR1)

    wiggle = bb.BluePrint()
    wiggle.insertSegment(0, sine, args=(10e6, 10e-3, 0, 0), dur=longdur)
    wiggle.setSR(SR1)

    blob = bb.BluePrint()
    blob.insertSegment(0, gauss, args=(25e-3, 12e-9, 0, 0), dur=longdur)
    blob.setSR(SR1)

    slope = bb.BluePrint()
    slope.insertSegment(0, ramp, (0, 15e-3), dur=longdur)
    slope.setSR(SR1)

    elem1 = bb.Element()
    elem1.addBluePrint(1, wait)
    elem1.addBluePrint(2, wait)
    elem1.addBluePrint(3, wait)

    elem2 = bb.Element()
    elem2.addBluePrint(1, wiggle)
    elem2.addBluePrint(2, slope)
    elem2.addBluePrint(3, blob)

    elem3 = elem1.copy()

    seq = Sequence()
    seq.setSR(SR1)
    seq.addElement(1, elem1)
    seq.addElement(2, elem2)
    seq.addElement(3, elem3)
    seq.setSequencingNumberOfRepetitions(1, 10)
    seq.setSequencingNumberOfRepetitions(3, 10)

    return seq


@pytest.fixture
def subseq2():
    """
    A small sequence meant to be used as a subsequence
    """

    longdur = 101e-9

    wait = bb.BluePrint()
    wait.insertSegment(0, ramp, args=(0, 0), dur=10e-9)
    wait.setSR(SR1)

    wiggle = bb.BluePrint()
    wiggle.insertSegment(0, sine, args=(10e6, 10e-3, 0, 0), dur=longdur)
    wiggle.setSR(SR1)

    blob = bb.BluePrint()
    blob.insertSegment(0, gauss, args=(25e-3, 12e-9, 0, 0), dur=longdur)
    blob.setSR(SR1)

    slope = bb.BluePrint()
    slope.insertSegment(0, ramp, (0, 15e-3), dur=longdur)
    slope.setSR(SR1)

    elem1 = bb.Element()
    elem1.addBluePrint(1, wait)
    elem1.addBluePrint(2, wait)
    elem1.addBluePrint(3, wait)

    elem2 = bb.Element()
    elem2.addBluePrint(1, wiggle)
    elem2.addBluePrint(2, slope)
    elem2.addBluePrint(3, blob)

    seq = Sequence()
    seq.setSR(SR1)
    seq.addElement(1, elem2)
    seq.addElement(2, elem1)
    seq.setSequencingNumberOfRepetitions(2, 15)

    return seq


@pytest.fixture
def noise_element():
    """
    An element consisting of arrays of noise
    """

    noise1 = np.random.randn(250)
    noise2 = np.random.randn(250)
    noise3 = np.random.randn(250)

    elem = bb.Element()
    elem.addArray(1, noise1, SR=SR1)
    elem.addArray(2, noise2, SR=SR1)
    elem.addArray(3, noise3, SR=SR1)

    return elem


@pytest.fixture
def bp_element():

    dur = 100e-9

    bp1 = bb.BluePrint()
    bp1.insertSegment(0, sine, (1e6, 10e-3, 0, 0), dur=dur)

    bp2 = bb.BluePrint()
    bp2.insertSegment(0, sine, (2e6, 10e-3, 0, np.pi/2), dur=dur)

    bp3 = bb.BluePrint()
    bp3.insertSegment(0, sine, (3e6, 10e-3, 0, -1), dur=dur)

    for bp in [bp1, bp2, bp3]:
        bp.setSR(SR1)

    elem = bb.Element()
    for ch, bp in enumerate([bp1, bp2, bp3]):
        elem.addBluePrint(ch+1, bp)

    return elem


@pytest.fixture
def master_sequence(subseq1, subseq2, bp_element, noise_element):
    """
    A sequence with subsequences and elements, some elements
    have ararys, some have blueprint. We try to aim wide.
    """

    seq = Sequence()
    seq.setSR(SR1)

    seq.addElement(1, noise_element)
    seq.addSubSequence(2, subseq1)
    seq.addElement(3, bp_element)
    seq.addSubSequence(4, subseq2)

    return seq


def test_forge(master_sequence):

    assert master_sequence.length_sequenceelements == 4

    forged_seq = master_sequence.forge()

    forged_sequence_schema.validate(forged_seq)

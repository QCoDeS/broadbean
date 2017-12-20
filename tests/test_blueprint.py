# Test suite for the BluePrint Object of the broadband package
#
# It is impossible to make a complete test of all the many possible blueprints.
# The strategy is to make a few representative (we hope!) blueprints and then
# assert that hitting them with all their methods results in new blueprints
# with the desired data attributes (the desired state)

import pytest
import broadbean as bb

ramp = bb.PulseAtoms.ramp
sine = bb.PulseAtoms.sine

tophat_SR = 2000


@pytest.fixture
def virgin_blueprint():
    """
    Return an empty instance of BluePrint
    """
    return bb.BluePrint()


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


@pytest.fixture
def blueprint_nasty():
    """
    Return a nasty blueprint trying to hit some corner cases
    """
    ns = bb.BluePrint()
    ns.insertSegment(0, 'waituntil', args=(1,))
    ns.insertSegment(1, ramp, (-1/3, 1/3), dur=0.1)
    ns.insertSegment(2, 'waituntil', args=(1+2/3,))
    ns.setSR(tophat_SR)

    ns.setSegmentMarker('ramp', (-0.1, 0.1), 1)
    ns.setSegmentMarker('waituntil2', (0, 2/3), 2)

    ns.marker1 = [(0, 0.1)]
    ns.marker2 = [(1, 0.1)]

    return ns

##################################################
# TEST STATIC METHODS


@pytest.mark.parametrize('inp, outp', [('', ''),
                                       ('test', 'test'),
                                       ('test3', 'test'),
                                       ('2test3', '2test'),
                                       ('123_', '123_'),
                                       ('123_4', '123_')])
def test_basename(inp, outp):
    assert bb.BluePrint._basename(inp) == outp


@pytest.mark.parametrize('notstring', [(1, 1.1, [], (),
                                        ('name1',),
                                        ['name2'])])
def test_basename_input(notstring):
    with pytest.raises(ValueError):
        bb.BluePrint._basename(notstring)


namelistsinout = [(['name', 'name'], ['name', 'name2']),
                  (['ramp', 'sine', 'ramp', 'sine'],
                   ['ramp', 'sine', 'ramp2', 'sine2']),
                  (['name2', 'name'], ['name', 'name2']),
                  (['n3', 'n2', 'n1'], ['n', 'n2', 'n3']),
                  (['n', '2n', 'ss1', 'ss3'], ['n', '2n', 'ss', 'ss2'])]


def test_make_names_unique0():
    inp = namelistsinout[0][0]
    outp = namelistsinout[0][1]
    assert bb.BluePrint._make_names_unique(inp) == outp


def test_make_names_unique1():
    inp = namelistsinout[1][0]
    outp = namelistsinout[1][1]
    assert bb.BluePrint._make_names_unique(inp) == outp


def test_make_names_unique2():
    inp = namelistsinout[2][0]
    outp = namelistsinout[2][1]
    assert bb.BluePrint._make_names_unique(inp) == outp


def test_make_names_unique3():
    inp = namelistsinout[3][0]
    outp = namelistsinout[3][1]
    assert bb.BluePrint._make_names_unique(inp) == outp


def test_make_names_unique4():
    inp = namelistsinout[4][0]
    outp = namelistsinout[4][1]
    assert bb.BluePrint._make_names_unique(inp) == outp


def test_make_names_unique_input():
    with pytest.raises(ValueError):
        bb.BluePrint._make_names_unique('name')

##################################################
# TEST BARE INITIALISATION


def test_creation(virgin_blueprint):
    assert isinstance(virgin_blueprint, bb.BluePrint)


@pytest.mark.parametrize("attribute, expected", [('_funlist', []),
                                                 ('_namelist', []),
                                                 ('_argslist', []),
                                                 ('_durslist', []),
                                                 ('marker1', []),
                                                 ('marker2', []),
                                                 ('_segmark1', []),
                                                 ('_segmark2', [])])
def test_bare_init(virgin_blueprint, attribute, expected):
    assert virgin_blueprint.__getattribute__(attribute) == expected

##################################################
# TEST WITH TOPHAT


@pytest.mark.parametrize("attribute, val", [('_funlist', [ramp, ramp, ramp]),
                                            ('_namelist',
                                             ['ramp', 'ramp2', 'ramp3']),
                                            ('_argslist',
                                             [(0, 0), (1, 1), (0, 0)]),
                                            ('_durslist',
                                             [1, 0.5, 1]),
                                            ('marker1', []),
                                            ('marker2', []),
                                            ('_segmark1', [(0, 0)]*3),
                                            ('_segmark2', [(0, 0)]*3)])
def test_tophat_init(blueprint_tophat, attribute, val):
    assert blueprint_tophat.__getattribute__(attribute) == val


@pytest.mark.parametrize("attribute, val", [('_funlist', [ramp, ramp, ramp]),
                                            ('_namelist',
                                             ['ramp', 'ramp2', 'ramp3']),
                                            ('_argslist',
                                             [(0, 0), (1, 1), (0, 0)]),
                                            ('_durslist',
                                             [1, 0.5, 1]),
                                            ('marker1', []),
                                            ('marker2', []),
                                            ('_segmark1', [(0, 0)]*3),
                                            ('_segmark2', [(0, 0)]*3)])
def test_tophat_copy(blueprint_tophat, attribute, val):
    new_bp = blueprint_tophat.copy()
    assert new_bp.__getattribute__(attribute) == val


@pytest.mark.parametrize('name, newdur, durslist',
                         [('ramp', 0.1, [0.1, 0.5, 1]),
                          ('ramp2', 0.1, [1, 0.1, 1]),
                          ('ramp3', 0.1, [1, 0.5, 0.1])])
def test_tophat_changeduration(blueprint_tophat, name, newdur, durslist):
    blueprint_tophat.changeDuration(name, newdur)
    assert blueprint_tophat._durslist == durslist


def test_tophat_changeduration_everywhere(blueprint_tophat):
    blueprint_tophat.changeDuration('ramp', 0.2, replaceeverywhere=True)
    assert blueprint_tophat._durslist == [0.2]*3


@pytest.mark.parametrize('newdur', [-1, 0.0, 1/(tophat_SR+1), None])
def test_tophat_changeduration_valueerror(blueprint_tophat, newdur):
    with pytest.raises(ValueError):
        blueprint_tophat.changeDuration('ramp', newdur)


@pytest.mark.parametrize('name, arg, newval, argslist',
                         [('ramp', 'start', -1, [(-1, 0), (1, 1), (0, 0)]),
                          ('ramp', 'stop', -1, [(0, -1), (1, 1), (0, 0)]),
                          ('ramp', 0, -1, [(-1, 0), (1, 1), (0, 0)]),
                          ('ramp', 1, -1, [(0, -1), (1, 1), (0, 0)]),
                          ('ramp2', 'stop', -1, [(0, 0), (1, -1), (0, 0)])])
def test_tophat_changeargument(blueprint_tophat, name, arg, newval, argslist):
    blueprint_tophat.changeArg(name, arg, newval)
    assert blueprint_tophat._argslist == argslist


@pytest.mark.parametrize('name, arg, newval, argslist',
                         [('ramp', 'start', -1, [(-1, 0), (-1, 1), (-1, 0)]),
                          ('ramp', 'stop', -1, [(0, -1), (1, -1), (0, -1)]),
                          ('ramp', 0, -1, [(-1, 0), (-1, 1), (-1, 0)]),
                          ('ramp', 1, -1, [(0, -1), (1, -1), (0, -1)])])
def test_tophat_changeargument_replaceeverywhere(blueprint_tophat, name,
                                                 arg, newval, argslist):
    blueprint_tophat.changeArg(name, arg, newval, replaceeverywhere=True)
    assert blueprint_tophat._argslist == argslist


@pytest.mark.parametrize('name, arg', [('ramp', 'freq'),
                                       ('ramp', -1),
                                       ('ramp', 2),
                                       ('ramp2', ''),
                                       ('ramp4', 1)])
def test_tophat_changeargument_valueerror(blueprint_tophat, name, arg):
    with pytest.raises(ValueError):
        blueprint_tophat.changeArg(name, arg, 0)


@pytest.mark.parametrize('pos, func, funlist',
                         [(0, ramp, [ramp, ramp, ramp, ramp]),
                          (-1, sine, [ramp, ramp, ramp, sine]),
                          (2, sine, [ramp, ramp, sine, ramp]),
                          (3, sine, [ramp, ramp, ramp, sine])])
def test_tophat_insert_funlist(blueprint_tophat, pos, func, funlist):
    blueprint_tophat.insertSegment(pos, func, args=(1, 0), dur=1)
    assert blueprint_tophat._funlist == funlist


newargs = (5, 5)


@pytest.mark.parametrize('pos, argslist',
                         [(0, [newargs, (0, 0), (1, 1), (0, 0)]),
                          (-1, [(0, 0), (1, 1), (0, 0), newargs]),
                          (2, [(0, 0), (1, 1), newargs, (0, 0)])])
def test_tophat_insert_argslist(blueprint_tophat, pos, argslist):
    blueprint_tophat.insertSegment(pos, ramp, newargs, dur=1)
    assert blueprint_tophat._argslist == argslist


@pytest.mark.parametrize('pos, name, namelist',
                         [(0, 'myramp', ['myramp', 'ramp', 'ramp2', 'ramp3']),
                          (-1, 'myramp', ['ramp', 'ramp2', 'ramp3', 'myramp']),
                          (2, 'ramp', ['ramp', 'ramp2', 'ramp3', 'ramp4'])])
def test_tophat_insert_namelist(blueprint_tophat, pos, name, namelist):
    blueprint_tophat.insertSegment(pos, ramp, newargs, name=name, dur=0.5)
    assert blueprint_tophat._namelist == namelist


@pytest.mark.parametrize('name', ['ramp', 'ramp2', 'ramp3', 'ramp4'])
def test_tophat_remove_namelist(blueprint_tophat, name):
    if name in blueprint_tophat._namelist:
        blueprint_tophat.removeSegment(name)
        assert blueprint_tophat._namelist == ['ramp', 'ramp2']
    else:
        with pytest.raises(KeyError):
            blueprint_tophat.removeSegment(name)


def test_tophat_remove_segmentmarker(blueprint_tophat):

    with pytest.raises(ValueError):
        blueprint_tophat.removeSegmentMarker('ramp', 3)
    with pytest.raises(ValueError):
        blueprint_tophat.removeSegmentMarker('no such name', 3)

    # Adding and removing should be equivalent to NOOP
    bpc = blueprint_tophat.copy()
    blueprint_tophat.setSegmentMarker('ramp', (0, 0.1), 1)
    blueprint_tophat.removeSegmentMarker('ramp', 1)
    assert bpc == blueprint_tophat

    with pytest.raises(KeyError):
        bpc.removeSegmentMarker('no such name', 1)


##################################################
# DUNDERDUNDER


def test_not_equal(blueprint_tophat):
    bpc = blueprint_tophat.copy()

    with pytest.raises(ValueError):
        bpc == '1'

    bpc.insertSegment(0, ramp, (0, 0), dur=1/3)

    assert (bpc == blueprint_tophat) is False

    bpc = blueprint_tophat.copy()
    blueprint_tophat.marker1 = [(0, 0.1)]
    bpc.marker2 = [(0, 0.1)]

    assert (bpc == blueprint_tophat) is False

    bpc = blueprint_tophat.copy()
    bpc.setSegmentMarker('ramp', (0, 0.1), 1)

    assert (bpc == blueprint_tophat) is False

    bpc = blueprint_tophat.copy()
    bpc.marker2 = [(0, 0.1)]

    assert (bpc == blueprint_tophat) is False

    bpc = blueprint_tophat.copy()
    blueprint_tophat.setSegmentMarker('ramp', (0, 0.1), 2)

    assert (bpc == blueprint_tophat) is False


def test_add_two_identical(blueprint_tophat):
    bp = blueprint_tophat
    bpc = bp.copy()
    new_bp1 = bpc + bp
    new_bp2 = bp + bpc

    assert new_bp1 == new_bp2
    assert new_bp1._namelist == ['ramp', 'ramp2', 'ramp3', 'ramp4', 'ramp5',
                                 'ramp6']
    assert new_bp1._argslist == bp._argslist + bp._argslist
    assert new_bp1._funlist == bp._funlist + bp._funlist
    assert new_bp1._segmark1 == bp._segmark1 + bp._segmark1
    assert new_bp1._segmark2 == bp._segmark2 + bp._segmark2
    assert new_bp1._durslist == bp._durslist + bp._durslist
    assert new_bp1.marker1 == bp.marker1 + bp.marker1
    assert new_bp1.marker2 == bp.marker2 + bp.marker2


def test_add_two_different(blueprint_tophat, blueprint_nasty):
    th = blueprint_tophat
    ns = blueprint_nasty

    bp = th + ns

    assert bp._namelist == ['ramp', 'ramp2', 'ramp3',
                            'waituntil', 'ramp4', 'waituntil2']
    assert bp._argslist == th._argslist + ns._argslist
    assert bp._funlist == th._funlist + ns._funlist
    assert bp._segmark1 == th._segmark1 + ns._segmark1
    assert bp._segmark2 == th._segmark2 + ns._segmark2
    assert bp._durslist == th._durslist + ns._durslist
    assert bp.marker1 == th.marker1 + ns.marker1
    assert bp.marker2 == th.marker2 + ns.marker2


##################################################
# MISC


def test_description(blueprint_nasty, blueprint_tophat):
    desc1 = blueprint_nasty.description
    desc2 = blueprint_tophat.description

    exp_keys = ['marker1_abs', 'marker1_rel', 'marker2_abs', 'marker2_rel',
                'segment_01', 'segment_02', 'segment_03']

    assert sorted(list(desc1.keys())) == sorted(exp_keys)
    assert sorted(list(desc2.keys())) == sorted(exp_keys)

# More to come...

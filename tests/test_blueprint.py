import pytest
import broadbean as bb


@pytest.fixture
def virgin_blueprint():
    """
    Return an empty instance of BluePrint
    """
    return bb.BluePrint()


##################################################
# TEST BARE INITIALISATION

def test_creation(virgin_blueprint):
    assert isinstance(virgin_blueprint, bb.BluePrint)


@pytest.mark.parametrize("attribute, expected", [('_funlist', []),
                                                 ('_namelist', []),
                                                 ('_argslist', []),
                                                 ('_tslist', [])])
def test_bob(virgin_blueprint, attribute, expected):
    assert virgin_blueprint.__getattribute__(attribute) == expected





# def test_creation_funlist(virgin_blueprint):
#     assert virgin_blueprint._funlist == []


# def test_creation_nameslist(virgin_blueprint):
#     assert virgin_blueprint._namelist == []


# def test_creation_argslist(virgin_blueprint):
#     assert virgin_blueprint._argslist == []


# def test_creation_tslist(virgin_blueprint):
#     assert virgin_blueprint._tslist == []


#def test_creation_durslist(virgin_blueprint):
#    assert virgin_blueprint._durslist == []

#def test_creation_marker1(vi

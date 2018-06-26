import pytest
import numpy as np

from qcodes.instrument.base import Instrument

from broadbean.routing import route


@pytest.fixture
def f_forged_sequence():
    return {0: {'type': 'element',
                'content': {0: {'data': {'chan1': np.array([1, 2, 3]),
                                         'MarkerChan1': np.array([1, 0, 1])},
                                'sequencing': {'nrep': 5,
                                               'trig_wait': 0}},
                            1: {'data': {'chan1': np.array([1, 2, 3]),
                                         'MarkerChan1': np.array([1, 0, 1])},
                                'sequencing': {'nrep': 5,
                                               'trig_wait': 0}}},
                'sequencing': {'nrep': 5,
                            'trig_wait': 0}},
            1: {'type': 'element',
                'content': {0: {'data': {'chan1': np.array([1, 2, 3]),
                                         'MarkerChan1': np.array([1, 0, 1])},
                                'sequencing': {'nrep': 5,
                                               'trig_wait': 0}},
                            1: {'data': {'chan1': np.array([1, 2, 3]),
                                         'MarkerChan1': np.array([1, 0, 1])},
                                'sequencing': {'nrep': 5,
                                               'trig_wait': 0}}},
                'sequencing': {'nrep': 5,
                            'trig_wait': 0}}
    }


@pytest.fixture
def f_route():
    return {'chan1': ('my_instrument', 1),
            'MarkerChan1': ('my_marker_instrument', '1M1')}


@pytest.fixture
def f_instrument():
    return Instrument('my_instrument')


def test_route(f_forged_sequence, f_route, f_instrument):
    new_seq = route(f_forged_sequence, f_route, f_instrument)
    new_keys = (new_seq[0]['content'][0]['data'].keys())
    old_keys = (f_forged_sequence[0]['content'][0]['data'].keys())
    # transformation has happened
    assert 1 in new_keys
    assert 'chan1' not in new_keys
    # original structure stays unchanged
    assert 1 not in old_keys
    assert 'chan1' in old_keys
    # Channels meant for the other instrument are not present
    assert '1M1' not in new_keys
    assert 'MarkerChan1' not in new_keys
    # original structure stays unchanged
    assert 'MarkerChan1' in old_keys


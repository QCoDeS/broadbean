from broadbean.tools import forged_sequence_dict_to_list

import numpy as np
def test_forged_sequence_dict_to_list():

    data = {0: {'type': 'element',
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
    ret = forged_sequence_list_to_dict(data)
    data[0]['content'][0]['data']['chan1'][0] = 0
    assert ret[0]['content'][0]['data']['chan1'][0] == 0
    data[0]['type'] = 'test'
    assert ret[0]['type'] == 'element'

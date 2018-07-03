import numpy as np
from schema import Schema, Or, Optional

channel_dict = {Or(str, int): np.ndarray}
sequencing_dict = {Optional(str): int}
fs_schema = Schema(
    [
        {'data': Or(
            [
                {'data': channel_dict,
                 'sequencing': sequencing_dict}
            ],
            channel_dict
            ),
         'sequencing': sequencing_dict
        }
    ]
)

fs_schema_old = Schema({int: {'type': Or('subsequence', 'element'),
                          'content': {int: {'data': {Or(str, int): {str: np.ndarray}},
                                            Optional('sequencing'): {Optional(str):
                                                                    int}}},
                          'sequencing': {Optional(str): int}}})

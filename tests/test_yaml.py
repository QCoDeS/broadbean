
import pytest
import numpy as np

import yaml
from broadbean import Segment, SegmentGroup, Element, Sequence
from broadbean.atoms import sine, ramp, flat, zero, marker_on, marker_off
from broadbean.types import ForgedSequenceType
from broadbean.plotting import plotter
from broadbean.tools import check_sequence_duration_consistent
from broadbean.transformations import make_delcarative_linear_transformation
from broadbean.loader import read_segment, read_element
import broadbean


@pytest.fixture
def f_yaml_file():
    file = """
 rabi:
    template_element:
        duration: total_duration
        segments:
            main_channel:
                - SegmentGroup:  # driving
                    duration: driving_stage_duration
                    segments:
                        - zero: {duration: initial_wait}
                        - flat: {duration: pi_2, amplitude: pulse_amplitude}
                        - zero: {duration: evolution_time}
                        - flat: {duration: pi, amplitude: pulse_amplitude}
                        - zero: {duration: evolution_time}
                        - flat: {duration: pi_2, amplitude: pulse_amplitude}
                    transformation:
                        type: declarative_linear_transformation
                        data:
                            - pi:
                                - [2, pi_2]
                            - initial_wait:
                                - [1, driving_stage_duration]
                                - [-2, pi_2]
                                - [-1, pi]
                                - [-2, evolution_time]
                - SegmentGroup:  # readout
                    duration: readout_stage_duration
                    segments:
                        - zero: {duration: readout_delay}
                        - flat: {duration: readout_duration, amplitude:readout_amplitude}
                        - zero: {duration: post_readout_duration}
            alazar_marker:
                - marker_off: {duration: driving_stage_duration}
                - marker_pulse:
                    duration: readout_stage_duration
                    delay: pre_marker_duration
                    marker_duration: readout_marker_duration
        transformation:
            type: declarative_linear_transformation
            data:
                - post_readout_duration:
                    - [1, readout_stage_duration]
                    - [-1, readout_delay]
                    - [-1, readout_duration]
                - pre_marker_duration:
                    - [1, readout_delay]
                    - [-1, readout_marker_delay]
        local_context:
        sequencing:
    initial_element:

"""
    return file

@pytest.fixture
def f_yaml_object(f_yaml_file):
    return yaml.load(f_yaml_file)


@pytest.fixture
def f_element(f_yaml_object):
    return f_yaml_object['rabi']['template_element']

@pytest.fixture
def f_segment(f_yaml_object):
    return f_yaml_object['rabi']['template_element']['segments']['main_channel'][0]

def test_read_segment(f_segment):
    seg = read_segment(f_segment)
    print(seg)

def test_read_element(f_element):
    elem = read_element(f_element)
    print(elem)

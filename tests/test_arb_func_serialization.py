"""
Test for arb_func serialization functionality in blueprint.py
"""

import json
import os
import tempfile

import numpy as np
import pytest

import broadbean as bb

##################################################
# FIXTURES


@pytest.fixture
def blueprint_with_lambda():
    """
    Return a blueprint with an arb_func using a lambda function
    """
    bp = bb.BluePrint()
    bp.setSR(1e9)

    lambda_func = lambda t, ampl: ampl * t * t
    kwargs = {"ampl": 2}

    bp.insertSegment(
        0, bb.PulseAtoms.arb_func, (lambda_func, kwargs), dur=1e-6, name="test_lambda"
    )
    return bp


@pytest.fixture
def blueprint_with_sine_lambda():
    """
    Return a blueprint with an arb_func using a sine wave lambda function
    """
    bp = bb.BluePrint()
    bp.setSR(1e9)

    bp.insertSegment(
        0,
        bb.PulseAtoms.arb_func,
        (
            lambda t, freq, ampl: ampl * np.sin(2 * np.pi * freq * t),
            {"freq": 1e6, "ampl": 1},
        ),
        dur=2e-6,
        name="sine_wave",
    )
    return bp


@pytest.fixture
def blueprint_with_func_source():
    """
    Return a blueprint with a dynamically created lambda with __func_source__ attribute
    """
    bp = bb.BluePrint()
    bp.setSR(1e9)

    lambda_str = "lambda t, ampl, freq: ampl * np.sin(2 * np.pi * freq * t)"
    eval_globals = {"np": np}
    lambda_func = eval(lambda_str, eval_globals)
    lambda_func.__func_source__ = lambda_str

    kwargs = {"ampl": 1.5, "freq": 1e6}
    bp.insertSegment(
        0, bb.PulseAtoms.arb_func, (lambda_func, kwargs), dur=2e-6, name="custom_wave"
    )
    return bp


##################################################
# HELPER FUNCTIONS


def get_arrays_from_blueprint(bp):
    """Helper function to generate arrays from a blueprint"""
    elem = bb.Element()
    elem.addBluePrint(1, bp)
    return elem.getArrays()


##################################################
# TEST ARB_FUNC LAMBDA SERIALIZATION


def test_arb_func_lambda_description_contains_func_type(blueprint_with_lambda):
    """Test that description contains func_type for lambda"""
    desc = blueprint_with_lambda.description
    args = desc["segment_01"]["arguments"]
    assert args["func_type"] == "lambda"


def test_arb_func_lambda_description_contains_source(blueprint_with_lambda):
    """Test that description contains func_source for lambda"""
    desc = blueprint_with_lambda.description
    args = desc["segment_01"]["arguments"]
    assert "lambda t, ampl: ampl * t * t" in args["func_source"]


def test_arb_func_lambda_description_contains_kwargs(blueprint_with_lambda):
    """Test that description contains kwargs for lambda"""
    desc = blueprint_with_lambda.description
    args = desc["segment_01"]["arguments"]
    assert args["kwargs"] == {"ampl": 2}


def test_arb_func_lambda_json_serialization(blueprint_with_lambda):
    """Test that arb_func description can be serialized to JSON"""
    desc = blueprint_with_lambda.description
    json_str = json.dumps(desc)
    desc_restored = json.loads(json_str)
    assert desc_restored["segment_01"]["arguments"]["func_type"] == "lambda"


def test_arb_func_lambda_blueprint_reconstruction(blueprint_with_lambda):
    """Test that blueprint can be reconstructed from description"""
    arrays_orig = get_arrays_from_blueprint(blueprint_with_lambda)

    desc = blueprint_with_lambda.description
    json_str = json.dumps(desc)
    desc_restored = json.loads(json_str)

    bp_restored = bb.BluePrint.blueprint_from_description(desc_restored)
    arrays_restored = get_arrays_from_blueprint(bp_restored)

    assert np.allclose(arrays_orig[1]["wfm"], arrays_restored[1]["wfm"])


def test_arb_func_lambda_mathematical_correctness(blueprint_with_lambda):
    """Test that restored waveform is mathematically correct"""
    arrays_orig = get_arrays_from_blueprint(blueprint_with_lambda)

    desc = blueprint_with_lambda.description
    bp_restored = bb.BluePrint.blueprint_from_description(desc)
    arrays_restored = get_arrays_from_blueprint(bp_restored)

    time_test = 0.5e-6
    kwargs = {"ampl": 2}
    expected = kwargs["ampl"] * time_test * time_test
    actual_idx = int(time_test * blueprint_with_lambda.SR)

    assert np.isclose(expected, arrays_orig[1]["wfm"][actual_idx])
    assert np.isclose(expected, arrays_restored[1]["wfm"][actual_idx])


##################################################
# TEST ARB_FUNC JSON FILE OPERATIONS


def test_arb_func_write_to_json(blueprint_with_sine_lambda):
    """Test that arb_func blueprint can be written to JSON file"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json_file_path = f.name

    try:
        blueprint_with_sine_lambda.write_to_json(json_file_path)
        assert os.path.exists(json_file_path)
    finally:
        if os.path.exists(json_file_path):
            os.unlink(json_file_path)


def test_arb_func_read_from_json(blueprint_with_sine_lambda):
    """Test that arb_func blueprint can be read from JSON file"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json_file_path = f.name

    try:
        blueprint_with_sine_lambda.write_to_json(json_file_path)
        bp_restored = bb.BluePrint.init_from_json(json_file_path)
        assert isinstance(bp_restored, bb.BluePrint)
    finally:
        if os.path.exists(json_file_path):
            os.unlink(json_file_path)


def test_arb_func_json_roundtrip_waveform_match(blueprint_with_sine_lambda):
    """Test that waveforms match after JSON file round-trip"""
    arrays_orig = get_arrays_from_blueprint(blueprint_with_sine_lambda)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json_file_path = f.name

    try:
        blueprint_with_sine_lambda.write_to_json(json_file_path)
        bp_restored = bb.BluePrint.init_from_json(json_file_path)
        arrays_restored = get_arrays_from_blueprint(bp_restored)

        assert np.allclose(arrays_orig[1]["wfm"], arrays_restored[1]["wfm"])
    finally:
        if os.path.exists(json_file_path):
            os.unlink(json_file_path)


##################################################
# TEST ARB_FUNC WITH __func_source__ ATTRIBUTE


def test_arb_func_func_source_attribute_func_type(blueprint_with_func_source):
    """Test that func_type is lambda for functions with __func_source__"""
    desc = blueprint_with_func_source.description
    args = desc["segment_01"]["arguments"]
    assert args["func_type"] == "lambda"


def test_arb_func_func_source_attribute_preserved(blueprint_with_func_source):
    """Test that __func_source__ attribute is used exactly as provided"""
    desc = blueprint_with_func_source.description
    args = desc["segment_01"]["arguments"]
    expected_source = "lambda t, ampl, freq: ampl * np.sin(2 * np.pi * freq * t)"
    assert args["func_source"] == expected_source


def test_arb_func_func_source_attribute_kwargs(blueprint_with_func_source):
    """Test that kwargs are preserved for functions with __func_source__"""
    desc = blueprint_with_func_source.description
    args = desc["segment_01"]["arguments"]
    assert args["kwargs"] == {"ampl": 1.5, "freq": 1e6}


def test_arb_func_func_source_json_roundtrip(blueprint_with_func_source):
    """Test JSON round-trip for functions with __func_source__"""
    arrays_orig = get_arrays_from_blueprint(blueprint_with_func_source)

    desc = blueprint_with_func_source.description
    json_str = json.dumps(desc)
    desc_restored = json.loads(json_str)
    bp_restored = bb.BluePrint.blueprint_from_description(desc_restored)

    arrays_restored = get_arrays_from_blueprint(bp_restored)

    assert np.allclose(arrays_orig[1]["wfm"], arrays_restored[1]["wfm"])


@pytest.mark.parametrize(
    "time_test, kwargs",
    [
        (0.5e-6, {"ampl": 1.5, "freq": 1e6}),
        (1.0e-6, {"ampl": 1.5, "freq": 1e6}),
        (1.5e-6, {"ampl": 1.5, "freq": 1e6}),
    ],
)
def test_arb_func_func_source_mathematical_correctness(
    blueprint_with_func_source, time_test, kwargs
):
    """Test mathematical correctness at various time points"""
    arrays_orig = get_arrays_from_blueprint(blueprint_with_func_source)

    desc = blueprint_with_func_source.description
    bp_restored = bb.BluePrint.blueprint_from_description(desc)
    arrays_restored = get_arrays_from_blueprint(bp_restored)

    expected = kwargs["ampl"] * np.sin(2 * np.pi * kwargs["freq"] * time_test)
    actual_idx = int(time_test * blueprint_with_func_source.SR)

    assert np.isclose(expected, arrays_orig[1]["wfm"][actual_idx], rtol=1e-3)
    assert np.isclose(expected, arrays_restored[1]["wfm"][actual_idx], rtol=1e-3)

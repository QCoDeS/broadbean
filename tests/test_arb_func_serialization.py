"""
Test for arb_func serialization functionality in blueprint.py
"""

import json
import numpy as np
import pytest

import broadbean as bb


def test_arb_func_lambda_serialization():
    """Test that arb_func with lambda functions can be serialized and deserialized correctly"""
    
    # Create blueprint with arb_func using lambda
    bp = bb.BluePrint()
    bp.setSR(1e9)
    
    # Use lambda function as in user example
    lambda_func = lambda t, ampl: ampl * t * t
    kwargs = {'ampl': 2}
    
    bp.insertSegment(0, bb.PulseAtoms.arb_func, (lambda_func, kwargs), dur=1e-6, name="test_lambda")
    
    # Generate original waveform
    elem_orig = bb.Element()
    elem_orig.addBluePrint(1, bp)
    arrays_orig = elem_orig.getArrays()
    
    # Test description contains proper serialization
    desc = bp.description
    args = desc["segment_01"]["arguments"]
    
    assert args["func_type"] == "lambda"
    assert "lambda t, ampl: ampl * t * t" in args["func_source"]
    assert args["kwargs"] == kwargs
    
    # Test JSON serialization works
    json_str = json.dumps(desc)
    desc_restored = json.loads(json_str)
    
    # Test blueprint reconstruction
    bp_restored = bb.BluePrint.blueprint_from_description(desc_restored)
    
    # Generate restored waveform
    elem_restored = bb.Element()
    elem_restored.addBluePrint(1, bp_restored)
    arrays_restored = elem_restored.getArrays()
    
    # Verify waveforms match
    assert np.allclose(arrays_orig[1]['wfm'], arrays_restored[1]['wfm'])
    
    # Verify mathematical correctness
    time_test = 0.5e-6
    expected = kwargs['ampl'] * time_test * time_test
    actual_idx = int(time_test * bp.SR)
    assert np.isclose(expected, arrays_orig[1]['wfm'][actual_idx])
    assert np.isclose(expected, arrays_restored[1]['wfm'][actual_idx])


def test_arb_func_json_file_operations():
    """Test that arb_func blueprints can be written to and read from JSON files"""
    
    bp = bb.BluePrint()
    bp.setSR(1e9)
    
    # Simple lambda for testing
    bp.insertSegment(0, bb.PulseAtoms.arb_func, 
                    (lambda t, freq, ampl: ampl * np.sin(2 * np.pi * freq * t), 
                     {'freq': 1e6, 'ampl': 1}), 
                    dur=2e-6, name="sine_wave")
    
    # Generate original arrays
    elem_orig = bb.Element()
    elem_orig.addBluePrint(1, bp)
    arrays_orig = elem_orig.getArrays()
    
    # Write to and read from JSON file
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json_file_path = f.name
    
    try:
        bp.write_to_json(json_file_path)
        bp_restored = bb.BluePrint.init_from_json(json_file_path)
        
        # Generate restored arrays
        elem_restored = bb.Element()
        elem_restored.addBluePrint(1, bp_restored)
        arrays_restored = elem_restored.getArrays()
        
        # Verify they match
        assert np.allclose(arrays_orig[1]['wfm'], arrays_restored[1]['wfm'])
        
    finally:
        import os
        if os.path.exists(json_file_path):
            os.unlink(json_file_path)
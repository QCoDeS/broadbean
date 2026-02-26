"""
Tests for the func_serialization module.

Covers serialization, deserialization, safe namespace restrictions,
and round-trip correctness.
"""

import numpy as np
import pytest

from broadbean.func_serialization import (
    _SAFE_EVAL_NAMESPACE,
    deserialize_function,
    serialize_function,
)

# ------------------------------------------------------------------
# Serialization tests
# ------------------------------------------------------------------


def test_serialize_lambda():
    """Lambda functions are serialized with func_type='lambda'"""
    func = lambda t, ampl: ampl * t  # noqa: E731
    result = serialize_function(func)
    assert result["func_type"] == "lambda"
    assert "lambda" in result["func_source"]


def test_serialize_named_function():
    """Named functions are serialized with func_type='named_function'"""

    def my_wave(t, ampl):
        return ampl * t

    result = serialize_function(my_wave)
    assert result["func_type"] == "named_function"
    assert result["func_name"] == "my_wave"
    assert "def my_wave" in result["func_source"]


def test_serialize_func_source_attribute():
    """Functions with __func_source__ use that attribute directly"""
    func = lambda t, a: a * t  # noqa: E731
    func.__func_source__ = "lambda t, a: a * t"
    result = serialize_function(func)
    assert result["func_type"] == "lambda"
    assert result["func_source"] == "lambda t, a: a * t"


# ------------------------------------------------------------------
# Deserialization tests
# ------------------------------------------------------------------


def test_deserialize_lambda():
    """A lambda source string can be deserialized to a working callable"""
    serialized = {
        "func_type": "lambda",
        "func_source": "lambda t, ampl: ampl * t",
    }
    func = deserialize_function(serialized)
    assert callable(func)
    assert func(2.0, ampl=3.0) == 6.0


def test_deserialize_lambda_with_numpy():
    """Lambda expressions can use np in the safe namespace"""
    serialized = {
        "func_type": "lambda",
        "func_source": "lambda t, freq: np.sin(2 * np.pi * freq * t)",
    }
    func = deserialize_function(serialized)
    result = func(0.25, freq=1.0)
    assert np.isclose(result, 1.0)


def test_deserialize_named_function():
    """A named function source can be deserialized"""
    source = "def my_func(t, ampl):\n    return ampl * t * t\n"
    serialized = {
        "func_type": "named_function",
        "func_name": "my_func",
        "func_source": source,
    }
    func = deserialize_function(serialized)
    assert callable(func)
    assert func(3.0, 2.0) == 18.0


def test_deserialize_named_function_with_numpy():
    """Named functions can use np in the safe namespace"""
    source = (
        "def wave(t, freq, ampl):\n    return ampl * np.sin(2 * np.pi * freq * t)\n"
    )
    serialized = {
        "func_type": "named_function",
        "func_name": "wave",
        "func_source": source,
    }
    func = deserialize_function(serialized)
    result = func(0.25, 1.0, 1.0)
    assert np.isclose(result, 1.0)


def test_deserialize_raises_on_none_source():
    """Deserialization raises ValueError when func_source is None"""
    serialized = {"func_type": "lambda", "func_source": None}
    with pytest.raises(ValueError, match="no source expression"):
        deserialize_function(serialized)


def test_deserialize_raises_on_unknown_type():
    """Deserialization raises ValueError for unknown func_type"""
    serialized = {
        "func_type": "unknown",
        "func_source": "lambda t: t",
    }
    with pytest.raises(ValueError, match="Unknown func_type"):
        deserialize_function(serialized)


def test_deserialize_raises_on_bad_source():
    """Deserialization raises ValueError for invalid source"""
    serialized = {
        "func_type": "lambda",
        "func_source": "this is not valid python!!!",
    }
    with pytest.raises(ValueError, match="Failed to evaluate"):
        deserialize_function(serialized)


def test_deserialize_named_missing_name():
    """Named function deserialization raises if name not found in executed source"""
    source = "def other_name(t):\n    return t\n"
    serialized = {
        "func_type": "named_function",
        "func_name": "expected_name",
        "func_source": source,
    }
    with pytest.raises(ValueError, match="not found after executing"):
        deserialize_function(serialized)


# ------------------------------------------------------------------
# Safety tests
# ------------------------------------------------------------------


def test_safe_namespace_no_builtins():
    """The safe namespace does not expose Python builtins"""
    assert _SAFE_EVAL_NAMESPACE["__builtins__"] == {}


def test_cannot_access_os_module():
    """Deserialized expressions cannot import or use os at call time"""
    serialized = {
        "func_type": "lambda",
        "func_source": "lambda: __import__('os').system('echo pwned')",
    }
    func = deserialize_function(serialized)
    with pytest.raises((NameError, TypeError)):
        func()


def test_cannot_use_open():
    """Deserialized expressions cannot use open() at call time"""
    serialized = {
        "func_type": "lambda",
        "func_source": "lambda: open('/etc/passwd')",
    }
    func = deserialize_function(serialized)
    with pytest.raises((NameError, TypeError)):
        func()


def test_named_function_no_globals_leak():
    """Named function exec does not have access to caller's globals"""
    source = "def bad(t):\n    return json.dumps({})\n"
    serialized = {
        "func_type": "named_function",
        "func_name": "bad",
        "func_source": source,
    }
    # Should reconstruct, but calling it should fail because json is not available
    func = deserialize_function(serialized)
    with pytest.raises(NameError):
        func(0)


# ------------------------------------------------------------------
# Round-trip tests
# ------------------------------------------------------------------


def test_roundtrip_lambda():
    """Serialize and deserialize a lambda, then verify it produces the same results"""
    original = lambda t, ampl: ampl * t * t  # noqa: E731
    serialized = serialize_function(original)
    restored = deserialize_function(serialized)

    t_test = np.linspace(0, 1, 100)
    np.testing.assert_allclose(original(t_test, ampl=2.0), restored(t_test, ampl=2.0))


def test_roundtrip_named_function():
    """Serialize and deserialize a named function"""

    def exponential_decay(t, ampl, tau):
        return ampl * np.exp(-t / tau)

    serialized = serialize_function(exponential_decay)
    restored = deserialize_function(serialized)

    t_test = np.linspace(0, 1e-6, 100)
    np.testing.assert_allclose(
        exponential_decay(t_test, 2.0, 0.33e-6),
        restored(t_test, 2.0, 0.33e-6),
    )


def test_roundtrip_func_source_attribute():
    """Round-trip a function created from a UI-provided source string"""
    source_str = "lambda t, ampl, tau: ampl * np.exp(-t / tau)"
    original = eval(source_str, {"np": np})  # noqa: S307
    original.__func_source__ = source_str

    serialized = serialize_function(original)
    assert serialized["func_source"] == source_str

    restored = deserialize_function(serialized)
    t_test = np.linspace(0, 1e-6, 100)
    np.testing.assert_allclose(
        original(t_test, ampl=2.0, tau=0.33e-6),
        restored(t_test, ampl=2.0, tau=0.33e-6),
    )

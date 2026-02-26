# Utilities for serializing and deserializing Python functions to/from strings.
#
# This module provides a safe, controlled way to store function expressions
# as strings (for JSON serialization) and reconstruct them later. It is
# designed for use with PulseAtoms.arb_func, where users define custom
# waveforms via lambda expressions or simple named functions.
#
# The serialization format stores a source expression string such as:
#   "lambda t, ampl, freq: ampl * np.sin(2 * np.pi * freq * t)"
#
# On deserialization, the expression is evaluated in a restricted namespace
# containing only numpy (as ``np``) and Python builtins. Functions that rely
# on other imports are not supported — they must be self-sufficient.

import inspect
import logging
import re
import textwrap

import numpy as np

log = logging.getLogger(__name__)

# The namespace available when deserializing function expressions.
# Only numpy is exposed; no access to the caller's globals.
_SAFE_EVAL_NAMESPACE: dict = {"np": np, "numpy": np, "__builtins__": {}}


def serialize_function(func_obj) -> dict:
    """
    Serialize a callable into a JSON-compatible dict.

    The dict always contains:
        - ``func_type``: either ``"lambda"`` or ``"named_function"``
        - ``func_source``: the source expression as a string, or ``None``
            if it could not be determined

    For named functions, ``func_name`` is also included.

    The source string must be *self-sufficient*: it may reference ``np``
    (numpy) but must not depend on any other imports or global state.

    If the callable carries a ``__func_source__`` attribute (e.g. set by
    an external UI), that value is used directly and no introspection is
    attempted.

    Args:
        func_obj: A callable (lambda or regular function).

    Returns:
        dict with serialization metadata.
    """
    # Prefer an explicitly attached source string (from an external UI, etc.)
    if hasattr(func_obj, "__func_source__"):
        return {
            "func_type": "lambda",
            "func_source": func_obj.__func_source__,
        }

    is_lambda = not (hasattr(func_obj, "__name__") and func_obj.__name__ != "<lambda>")

    if is_lambda:
        func_source = _extract_lambda_source(func_obj)
        return {
            "func_type": "lambda",
            "func_source": func_source,
        }
    else:
        func_source = _extract_named_function_source(func_obj)
        return {
            "func_type": "named_function",
            "func_name": func_obj.__name__,
            "func_source": func_source,
        }


def deserialize_function(serialized: dict):
    """
    Reconstruct a callable from a serialization dict produced by
    :func:`serialize_function`.

    Evaluation is performed in a restricted namespace that only exposes
    ``numpy`` (as both ``np`` and ``numpy``). No caller globals are
    available; the function expression must be self-sufficient.

    Args:
        serialized: A dict with at least ``func_type`` and ``func_source``.

    Returns:
        A callable reconstructed from the source expression.

    Raises:
        ValueError: If ``func_source`` is ``None`` (cannot reconstruct).
    """
    func_source = serialized.get("func_source")
    func_type = serialized.get("func_type")

    if func_source is None:
        raise ValueError(
            "Cannot deserialize function: no source expression was stored. "
            "Ensure the function was serialized with a valid source string."
        )

    if func_type == "lambda":
        return _eval_expression(func_source)
    elif func_type == "named_function":
        func_name = serialized.get("func_name")
        return _exec_named_function(func_source, func_name)
    else:
        raise ValueError(f"Unknown func_type: {func_type!r}")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _extract_lambda_source(func_obj) -> str | None:
    """
    Attempt to extract the lambda expression source from a callable.

    Uses :func:`inspect.getsource` and a regex to isolate the lambda
    expression. Returns ``None`` on failure.
    """
    try:
        raw_source = inspect.getsource(func_obj)
    except (OSError, TypeError):
        return None

    # Extract the lambda expression from the (possibly multi-line) source.
    # The regex matches "lambda <params>: <body>" up to the first unbalanced
    # comma, semicolon, or newline.
    match = re.search(r"lambda\s+[^:]*:\s*[^\n,;]+", raw_source)
    if match:
        return match.group(0).strip()
    return None


def _extract_named_function_source(func_obj) -> str | None:
    """
    Attempt to extract the full source of a named function.

    Returns ``None`` on failure.
    """
    try:
        return inspect.getsource(func_obj)
    except (OSError, TypeError):
        return None


def _eval_expression(source: str):
    """
    Evaluate a lambda expression string in the safe namespace.

    Args:
        source: e.g. ``"lambda t, ampl: ampl * t"``

    Returns:
        The resulting callable.
    """
    try:
        return eval(source, _SAFE_EVAL_NAMESPACE)  # noqa: S307
    except Exception as e:
        log.warning("Could not reconstruct function from source %r: %s", source, e)
        raise ValueError(f"Failed to evaluate function expression: {source!r}") from e


def _exec_named_function(source: str, func_name: str):
    """
    Execute a named function definition in the safe namespace and return
    the resulting callable.

    Args:
        source: The full function source code.
        func_name: The expected function name to retrieve after exec.

    Returns:
        The reconstructed callable.
    """
    local_ns: dict = {}
    try:
        exec(textwrap.dedent(source), _SAFE_EVAL_NAMESPACE, local_ns)  # noqa: S102
    except Exception as e:
        log.warning(
            "Could not reconstruct named function %r from source: %s",
            func_name,
            e,
        )
        raise ValueError(f"Failed to execute function source for {func_name!r}") from e

    if func_name not in local_ns:
        raise ValueError(
            f"Function {func_name!r} not found after executing source code."
        )
    return local_ns[func_name]

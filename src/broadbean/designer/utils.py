"""Pure utility functions for waveform designer.

These functions contain no Django or hardware dependencies and can be tested
with fast unit tests.
"""

import json
import re

import numpy as np


def index_to_letters(index: int) -> str:
    """Convert numeric index to letter suffix.

    Examples:
        0 -> 'a', 1 -> 'b', ..., 25 -> 'z', 26 -> 'aa', 27 -> 'ab', etc.

    Args:
        index: Zero-based index to convert.

    Returns:
        Letter representation of the index.
    """
    result = ""
    index += 1  # Make it 1-indexed for easier calculation
    while index > 0:
        index -= 1  # Adjust for 0-based modulo
        result = chr(ord("a") + (index % 26)) + result
        index //= 26
    return result if result else "a"


def rewrite_lambda_for_numpy(lambda_str: str) -> str:
    """Rewrite lambda expression to use numpy functions.

    This ensures the lambda works when deserialized by broadbean.

    Replaces bare function calls with np.function equivalents:
    - exp(x) -> np.exp(x)
    - sin(x) -> np.sin(x)
    - cos(x) -> np.cos(x)
    - log(x) -> np.log(x)
    - sqrt(x) -> np.sqrt(x)
    - pi -> np.pi

    Args:
        lambda_str: Lambda expression string to rewrite.

    Returns:
        Rewritten lambda string with numpy function calls.
    """
    # Map of function names to their numpy equivalents
    math_functions = [
        "exp",
        "sin",
        "cos",
        "tan",
        "log",
        "log10",
        "sqrt",
        "abs",
        "floor",
        "ceil",
        "sinh",
        "cosh",
        "tanh",
    ]

    rewritten = lambda_str

    # Replace standalone 'pi' with 'np.pi' (not part of a word, not already prefixed with np.)
    rewritten = re.sub(r"(?<!np\.)\bpi\b", "np.pi", rewritten)

    # Replace function calls: func( -> np.func(
    # Use negative lookbehind to avoid replacing functions already prefixed with np.
    for func in math_functions:
        # Match function name followed by opening parenthesis, but not if preceded by 'np.'
        pattern = r"(?<!np\.)\b" + func + r"\s*\("
        replacement = f"np.{func}("
        rewritten = re.sub(pattern, replacement, rewritten)

    return rewritten


def map_ui_param_to_broadbean_arg(segment_type: str, ui_param_name: str) -> str:
    """Map UI parameter names to broadbean internal argument names.

    Args:
        segment_type: Type of segment ('sine', 'gaussian', 'ramp', etc.)
        ui_param_name: Parameter name used in UI

    Returns:
        Broadbean internal argument name.
    """
    mapping = {
        "sine": {
            "frequency": "freq",
            "amplitude": "ampl",
            "offset": "off",
            "phase": "phase",
        },
        "gaussian": {
            "amplitude": "ampl",
            "width": "sigma",
            "center": "mu",
            "offset": "offset",
        },
        "ramp": {
            "start": "start",
            "stop": "stop",
        },
        "exponential": {
            "amplitude": "amplitude",
            "time_constant": "tau",
        },
    }

    return mapping.get(segment_type, {}).get(ui_param_name, ui_param_name)


def parse_element_data_to_ui_format(element_data: dict) -> list:
    """Parse broadbean element_data JSON to UI-friendly channel/segment format.

    Args:
        element_data: Dictionary containing broadbean Element JSON structure

    Returns:
        List of channels with segments in UI format for the designer
    """
    if not element_data or not isinstance(element_data, dict):
        return []

    channels = []

    # Get all channel numbers (keys that are digits)
    channel_nums = sorted([int(k) for k in element_data.keys() if k.isdigit()])

    for channel_num in channel_nums:
        channel_data = element_data[str(channel_num)]

        # Build channel object
        channel = {"name": f"Channel {channel_num}", "segments": []}

        # Get all segment keys and sort them
        segment_keys = sorted(
            [k for k in channel_data.keys() if k.startswith("segment_")]
        )

        for seg_key in segment_keys:
            seg_data = channel_data[seg_key]

            if not isinstance(seg_data, dict):
                continue

            # Extract segment information from broadbean format
            segment_name = seg_data.get("name", "")
            function_type = seg_data.get("function", "ramp")

            # Map broadbean function types to UI segment types
            # Broadbean uses "function PulseAtoms.xxx" format
            if "PulseAtoms.ramp" in function_type:
                segment_type = "ramp"
            elif "PulseAtoms.sine" in function_type:
                segment_type = "sine"
            elif "PulseAtoms.gaussian" in function_type:
                segment_type = "gaussian"
            elif "arb_func" in function_type:
                segment_type = "custom"
            elif "waituntil" in function_type:
                segment_type = "waituntil"
            else:
                segment_type = "ramp"  # Default

            # Get duration from broadbean JSON (note: it's "durations" plural, not "duration")
            # For waituntil, duration is null in JSON
            duration = seg_data.get("durations")
            if duration is None:
                duration = 0  # waituntil segments

            # Get arguments dict (broadbean uses "arguments" not "args")
            arguments = seg_data.get("arguments", {})

            # Build segment object
            segment = {
                "type": segment_type,
                "name": segment_name,
                "duration": duration,
                "parameters": {},
                "markers": {},
            }

            # Extract parameters based on segment type
            if segment_type == "ramp":
                # Broadbean format: {"start": 0.25, "stop": 0.25}
                segment["parameters"]["start"] = arguments.get("start", 0.0)
                segment["parameters"]["stop"] = arguments.get("stop", 1.0)

            elif segment_type == "sine":
                # Broadbean format: {"freq": 10000000, "ampl": 0.25, "off": 0, "phase": 0.0}
                segment["parameters"]["frequency"] = arguments.get("freq", 1e6)
                segment["amplitude"] = arguments.get("ampl", 1.0)
                segment["parameters"]["offset"] = arguments.get("off", 0.0)
                phase_radians = arguments.get("phase", 0.0)
                segment["parameters"]["phase"] = (
                    phase_radians * 180 / np.pi
                )  # Convert to degrees

            elif segment_type == "gaussian":
                # Broadbean format: {"ampl": 1, "sigma": 1e-07, "mu": 0, "offset": 0.0}
                segment["amplitude"] = arguments.get("ampl", 1.0)
                # Broadbean uses "sigma" for width and "mu" for center
                segment["parameters"]["width"] = arguments.get(
                    "sigma", duration / 4 if duration else 1e-6
                )
                segment["parameters"]["center"] = arguments.get(
                    "mu", duration / 2 if duration else 5e-7
                )
                segment["parameters"]["offset"] = arguments.get("offset", 0.0)

            elif segment_type == "waituntil":
                # Broadbean format: {"waittime": [3e-07]}
                waittime_list = arguments.get("waittime", [1e-6])
                if isinstance(waittime_list, list) and len(waittime_list) > 0:
                    segment["parameters"]["absolute_time"] = waittime_list[0]
                else:
                    segment["parameters"]["absolute_time"] = 1e-6

            elif segment_type == "custom":
                # Broadbean format for arb_func (exponential/custom):
                # {"func_type": "lambda", "func_source": "lambda t, ...: ...", "kwargs": {...}}
                func_source = arguments.get("func_source", "")
                kwargs = arguments.get("kwargs", {})

                if func_source:
                    # Extract expression from lambda string (remove "lambda " prefix)
                    if func_source.startswith("lambda "):
                        expression = func_source[7:]  # Remove "lambda " prefix
                        segment["parameters"]["expression"] = expression
                    else:
                        segment["parameters"]["expression"] = func_source

                # Store kwargs as params_json
                if kwargs:
                    segment["parameters"]["params_json"] = json.dumps(kwargs)

            # Extract marker information
            if "marker1" in seg_data:
                marker1 = seg_data["marker1"]
                if isinstance(marker1, (list, tuple)) and len(marker1) >= 2:
                    segment["markers"]["marker1"] = {
                        "delay": marker1[0],
                        "duration": marker1[1],
                    }

            if "marker2" in seg_data:
                marker2 = seg_data["marker2"]
                if isinstance(marker2, (list, tuple)) and len(marker2) >= 2:
                    segment["markers"]["marker2"] = {
                        "delay": marker2[0],
                        "duration": marker2[1],
                    }

            channel["segments"].append(segment)

        channels.append(channel)

    return channels

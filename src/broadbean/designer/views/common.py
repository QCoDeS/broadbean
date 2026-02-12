"""Common utilities and helper functions for waveform designer views."""

import json
import logging
import numpy as np
from broadbean.blueprint import BluePrint
from broadbean.broadbean import PulseAtoms
from broadbean.element import Element
from broadbean.sequence import Sequence

from ..models import WaveformElement
from ..utils import (
    index_to_letters,
    rewrite_lambda_for_numpy,
    parse_element_data_to_ui_format,
)

logger = logging.getLogger(__name__)

# Global instances for instruments
_awg_instance = None
_scope_instance = None
_active_awg_config_id = None
_active_scope_config_id = None


def _build_blueprint(segments, sample_rate) -> BluePrint:
    """Build a BluePrint for a channel from multiple segments."""
    bp = BluePrint()
    bp.setSR(sample_rate)

    for seg_idx, segment in enumerate(segments):
        segment_type = segment.get("type", "ramp")
        parameters = segment.get("parameters", {})
        duration = segment.get("duration", 1e-6)

        # Get segment name from the segment data if available
        user_seg_name = segment.get("name", "")
        if user_seg_name:
            seg_name = user_seg_name
        else:
            letter_suffix = index_to_letters(seg_idx)
            seg_name = f"{segment_type}_{letter_suffix}"

        # Insert segment based on type
        if segment_type == "ramp":
            start_amplitude = parameters.get("start", 0.0)
            end_amplitude = parameters.get("stop", 1.0)
            bp.insertSegment(
                seg_idx,
                PulseAtoms.ramp,
                (start_amplitude, end_amplitude),
                name=seg_name,
                dur=duration,
            )

        elif segment_type == "sine":
            amplitude = segment.get("amplitude", 1.0)
            frequency = parameters.get("frequency", 1e6)
            phase_degrees = parameters.get("phase", 0)
            offset = parameters.get("offset", 0.0)
            phase_radians = phase_degrees * np.pi / 180
            bp.insertSegment(
                seg_idx,
                PulseAtoms.sine,
                (frequency, amplitude, offset, phase_radians),
                name=seg_name,
                dur=duration,
            )

        elif segment_type == "gaussian":
            amplitude = segment.get("amplitude", 1.0)
            width = parameters.get("width", duration / 4)
            center = parameters.get("center", duration / 2)
            offset = parameters.get("offset", 0.0)
            bp.insertSegment(
                seg_idx,
                PulseAtoms.gaussian,
                (amplitude, width, center, offset),
                name=seg_name,
                dur=duration,
            )

        elif segment_type == "exponential":
            amplitude = segment.get("amplitude", 1.0)
            time_constant = parameters.get("time_constant", duration / 3)
            exp_type = parameters.get("type", "rise")

            if exp_type == "decay":
                bp.insertSegment(
                    seg_idx,
                    PulseAtoms.arb_func,
                    (
                        lambda t, amplitude, tau: amplitude * np.exp(-t / tau),
                        {"amplitude": amplitude, "tau": time_constant},
                    ),
                    name=seg_name,
                    dur=duration,
                )
            else:
                bp.insertSegment(
                    seg_idx,
                    PulseAtoms.arb_func,
                    (
                        lambda t, amplitude, tau: amplitude * (1 - np.exp(-t / tau)),
                        {"amplitude": amplitude, "tau": time_constant},
                    ),
                    name=seg_name,
                    dur=duration,
                )

        elif segment_type == "waituntil":
            absolute_time = parameters.get("absolute_time", 1e-6)
            bp.insertSegment(
                seg_idx,
                "waituntil",
                absolute_time,
                name=seg_name,
            )

        elif segment_type == "custom":
            expression = parameters.get("expression", "t: 0*t")
            params_json = parameters.get("params_json", "{}")

            if ":" not in expression:
                raise ValueError("Expression must contain ':' separator")

            args_str, body_str = expression.split(":", 1)
            args_list = [arg.strip() for arg in args_str.split(",")]

            if not args_list or args_list[0] != "t":
                raise ValueError("First parameter must be 't'")

            params = json.loads(params_json)

            param_names = args_list[1:]
            for param_name in param_names:
                if param_name not in params:
                    raise ValueError(
                        f"Parameter '{param_name}' not found in parameters JSON"
                    )

            lambda_str = f"lambda {args_str}: {body_str.strip()}"
            lambda_str_rewritten = rewrite_lambda_for_numpy(lambda_str)

            eval_globals = {
                "__builtins__": {},
                "np": np,
                "sin": np.sin,
                "cos": np.cos,
                "exp": np.exp,
                "log": np.log,
                "sqrt": np.sqrt,
                "pi": np.pi,
            }

            lambda_func = eval(lambda_str_rewritten, eval_globals)
            lambda_func.__func_source__ = lambda_str_rewritten

            bp.insertSegment(
                seg_idx,
                PulseAtoms.arb_func,
                (lambda_func, params),
                name=seg_name,
                dur=duration,
            )

        else:
            amplitude = segment.get("amplitude", 1.0)
            bp.insertSegment(
                seg_idx,
                PulseAtoms.ramp,
                (amplitude, amplitude),
                name=seg_name,
                dur=duration,
            )

        # Add markers if present
        markers = segment.get("markers", {})
        if markers:
            marker1_data = markers.get("marker1", {})
            if marker1_data and isinstance(marker1_data, dict):
                delay = marker1_data.get("delay", 0)
                marker_duration = marker1_data.get("duration", 0)
                if marker_duration > 0:
                    bp.setSegmentMarker(seg_name, (delay, marker_duration), 1)

            marker2_data = markers.get("marker2", {})
            if marker2_data and isinstance(marker2_data, dict):
                delay = marker2_data.get("delay", 0)
                marker_duration = marker2_data.get("duration", 0)
                if marker_duration > 0:
                    bp.setSegmentMarker(seg_name, (delay, marker_duration), 2)
    return bp


def _build_element(channels, sample_rate) -> Element:
    """Build an Element from channel data."""
    elem = Element()

    for channel_idx, channel in enumerate(channels):
        channel_segments = channel.get("segments", [])

        if channel_segments:
            bp = _build_blueprint(channel_segments, sample_rate)
            elem.addBluePrint(channel_idx + 1, bp)
    return elem


def _build_sequence(sequence_elements):
    """Build a broadbean Sequence from sequence element data."""
    seq = Sequence()

    first_elem_id = sequence_elements[0].get("element_id")
    first_elem_model = WaveformElement.objects.get(id=first_elem_id)
    sample_rate = first_elem_model.sample_rate

    for seq_elem_data in sequence_elements:
        element_id = seq_elem_data.get("element_id")
        position = seq_elem_data.get("position")

        elem_model = WaveformElement.objects.get(id=element_id)
        channels = parse_element_data_to_ui_format(elem_model.element_data)
        elem = _build_element(channels, elem_model.sample_rate)
        seq.addElement(position, elem)

    seq.setSR(sample_rate)

    for seq_elem_data in sequence_elements:
        position = seq_elem_data.get("position")
        trigger_input = seq_elem_data.get("trigger_input", 0)
        repetitions = seq_elem_data.get("repetitions", 1)
        goto = seq_elem_data.get("goto")
        flags = seq_elem_data.get("flags")

        seq.setSequencingNumberOfRepetitions(position, repetitions)
        seq.setSequencingTriggerWait(position, trigger_input)
        seq.setSequencingEventJumpTarget(position, 0)

        if goto is not None:
            seq.setSequencingGoto(position, goto)

        if flags and isinstance(flags, dict):
            elem = seq.element(position)
            for channel_key, flag_list in flags.items():
                if channel_key.startswith("channel_"):
                    channel_num = int(channel_key.split("_")[1])
                    if isinstance(flag_list, list) and len(flag_list) == 4:
                        elem.addFlags(channel_num, flag_list)

    for channel in seq.channels:
        seq.setChannelAmplitude(channel, 0.5)
        seq.setChannelOffset(channel, 0.0)

    total_duration = 0
    for seq_elem_data in sequence_elements:
        elem_model = WaveformElement.objects.get(id=seq_elem_data["element_id"])
        repetitions = seq_elem_data.get("repetitions", 1)
        total_duration += elem_model.duration * repetitions

    return seq, sample_rate, total_duration


def _get_instruments(awg_config_id, scope_config_id):
    """Get or create AWG and Scope instances based on separate configurations.

    Uses the AWGFactory and ScopeFactory to create appropriate instrument instances
    (mock or real hardware) based on the configuration settings stored in the
    AWGStationConfig and ScopeStationConfig models.

    Args:
        awg_config_id: ID of the AWGStationConfig to use
        scope_config_id: ID of the ScopeStationConfig to use

    Returns:
        Tuple of (awg, scope) instrument instances
    """
    global _awg_instance, _scope_instance, _active_awg_config_id, _active_scope_config_id

    # Import here to avoid circular imports
    from ..models import AWGStationConfig, ScopeStationConfig
    from broadbean.interface.awg import AWGFactory
    from broadbean.interface.scope import ScopeFactory

    # If we already have instruments for these configs, return them
    if (
        _active_awg_config_id == awg_config_id
        and _active_scope_config_id == scope_config_id
        and _awg_instance is not None
        and _scope_instance is not None
    ):
        return _awg_instance, _scope_instance

    # Disconnect existing instruments if switching configs
    if _awg_instance is not None or _scope_instance is not None:
        logger.info(
            f"Switching configs (AWG: {_active_awg_config_id} -> {awg_config_id}, "
            f"Scope: {_active_scope_config_id} -> {scope_config_id}), "
            "disconnecting existing instruments"
        )
        if _awg_instance is not None:
            try:
                _awg_instance.disconnect()
            except Exception as e:
                logger.warning(f"Error disconnecting AWG: {e}")
        if _scope_instance is not None:
            try:
                _scope_instance.disconnect()
            except Exception as e:
                logger.warning(f"Error disconnecting Scope: {e}")
        _awg_instance = None
        _scope_instance = None

    # Load the AWG configuration from the database
    awg_config_model = AWGStationConfig.objects.get(id=awg_config_id)
    logger.info(
        f"Creating AWG with config: is_mock={awg_config_model.is_mock}, "
        f"address={awg_config_model.address}"
    )

    # Load the Scope configuration from the database
    scope_config_model = ScopeStationConfig.objects.get(id=scope_config_id)
    logger.info(
        f"Creating Scope with config: is_mock={scope_config_model.is_mock}, "
        f"address={scope_config_model.address}"
    )

    # Use factories to create the appropriate instruments from models
    _awg_instance = AWGFactory.create_from_model(awg_config_model)
    _scope_instance = ScopeFactory.create_from_model(scope_config_model)
    _active_awg_config_id = awg_config_id
    _active_scope_config_id = scope_config_id

    return _awg_instance, _scope_instance


def reset_instrument_instances():
    """Reset global instrument instances. Used by disconnect_instruments."""
    global _awg_instance, _scope_instance, _active_awg_config_id, _active_scope_config_id
    _awg_instance = None
    _scope_instance = None
    _active_awg_config_id = None
    _active_scope_config_id = None

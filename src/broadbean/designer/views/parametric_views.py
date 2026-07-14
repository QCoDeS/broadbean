"""Views for the parametric generator interface (parametric_generator.html)."""

import json

import numpy as np
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from broadbean.tools import makeVaryingSequence

from ..models import SequenceElement, WaveformElement, WaveformSequence
from ..utils import map_ui_param_to_broadbean_arg, parse_element_data_to_ui_format
from .common import _build_element, _build_sequence


def parametric_generator_view(request):
    """Parametric sequence generator interface view."""
    return render(request, "waveform_designer/parametric_generator.html")


@csrf_exempt
@require_http_methods(["POST"])
def generate_parametric_sequence(request):
    """Generate and save a parametric sequence using broadbean's makeVaryingSequence."""
    try:
        data = json.loads(request.body)

        element_id = data.get("element_id")
        loop_iterations = data.get("loop_iterations", [])
        parameters_by_loop = data.get("parameters", {})
        name = data.get("name", "Parametric Sequence")
        description = data.get("description", "")

        trigger_input = data.get("trigger_input", 1)
        repetitions = data.get("repetitions", 1)
        flags = data.get("flags", {})

        if not element_id:
            return JsonResponse(
                {"success": False, "error": "element_id is required"}, status=400
            )

        base_element_model = WaveformElement.objects.get(id=element_id)
        channels = parse_element_data_to_ui_format(base_element_model.element_data)
        base_elem = _build_element(channels, base_element_model.sample_rate)

        if isinstance(base_element_model.element_data, dict):
            element_data_json = base_element_model.element_data
        else:
            element_data_json = json.loads(base_element_model.element_data)

        segment_name_map = {}
        for channel_str, channel_data in element_data_json.items():
            if not channel_str.isdigit():
                continue
            channel_idx = int(channel_str) - 1

            segment_keys = sorted(
                [k for k in channel_data.keys() if k.startswith("segment_")]
            )

            for segment_idx, seg_key in enumerate(segment_keys):
                value = channel_data[seg_key]
                if isinstance(value, dict):
                    actual_segment_name = value.get("name", "")
                    if actual_segment_name:
                        segment_name_map[(channel_idx, segment_idx)] = (
                            actual_segment_name
                        )

        channels_list = []
        names_list = []
        args_list = []
        iters_list = []

        param_iteration_arrays = {}

        for loop_idx_str, params in parameters_by_loop.items():
            loop_idx = int(loop_idx_str)
            n_iterations = loop_iterations[loop_idx]

            for param_config in params:
                channel = param_config["channel"]
                segment_name_from_ui = param_config["segment_name"]
                segment_idx = param_config.get("segment_index")
                parameter = param_config["parameter"]
                start = param_config["start"]
                stop = param_config["stop"]
                interpolation = param_config.get("interpolation", "linear")

                channel_idx = channel - 1

                if segment_idx is None:
                    if channel_idx < len(channels):
                        channel_segments = channels[channel_idx].get("segments", [])
                        for idx, seg in enumerate(channel_segments):
                            if seg.get("name") == segment_name_from_ui:
                                segment_idx = idx
                                break

                if (
                    segment_idx is not None
                    and (channel_idx, segment_idx) in segment_name_map
                ):
                    actual_segment_name = segment_name_map[(channel_idx, segment_idx)]
                else:
                    actual_segment_name = segment_name_from_ui

                if interpolation == "log":
                    if start <= 0 or stop <= 0:
                        return JsonResponse(
                            {
                                "success": False,
                                "error": f"Logarithmic interpolation requires positive values for {parameter}",
                            },
                            status=400,
                        )
                    param_values = np.logspace(
                        np.log10(start), np.log10(stop), n_iterations
                    ).tolist()
                else:
                    param_values = np.linspace(start, stop, n_iterations).tolist()

                param_key = f"ch{channel}_{actual_segment_name}_{parameter}"
                param_iteration_arrays[param_key] = {
                    "channel": channel,
                    "segment_name": actual_segment_name,
                    "parameter": parameter,
                    "values": param_values,
                    "loop": loop_idx,
                }

        total_elements = 1
        for n in loop_iterations:
            total_elements *= n

        def generate_indices(loop_lengths):
            if not loop_lengths:
                yield []
                return
            for i in range(loop_lengths[0]):
                for rest in generate_indices(loop_lengths[1:]):
                    yield [i] + rest

        for param_key, param_data in param_iteration_arrays.items():
            channel = param_data["channel"]
            segment_name = param_data["segment_name"]
            parameter = param_data["parameter"]
            values = param_data["values"]
            param_loop = param_data["loop"]

            channel_idx = channel - 1
            segment_type = None
            if channel_idx < len(channels):
                channel_segments = channels[channel_idx].get("segments", [])
                for seg in channel_segments:
                    if seg.get("name") == segment_name:
                        segment_type = seg.get("type")
                        break

            if segment_type:
                broadbean_param = map_ui_param_to_broadbean_arg(segment_type, parameter)
            else:
                broadbean_param = parameter

            full_iteration_list = []

            for indices in generate_indices(loop_iterations):
                value_idx = indices[param_loop]
                value = values[value_idx]

                if segment_type == "sine" and parameter == "phase":
                    value = value * np.pi / 180

                full_iteration_list.append(value)

            channels_list.append(channel)
            names_list.append(segment_name)
            args_list.append(broadbean_param)
            iters_list.append(full_iteration_list)

        if iters_list:
            expected_length = len(iters_list[0])
            if not all(len(iter_list) == expected_length for iter_list in iters_list):
                return JsonResponse(
                    {
                        "success": False,
                        "error": "Internal error: iteration lists have different lengths",
                    },
                    status=400,
                )

        try:
            varying_seq = makeVaryingSequence(
                base_elem, channels_list, names_list, args_list, iters_list
            )
        except Exception as e:
            return JsonResponse(
                {
                    "success": False,
                    "error": f"Failed to create varying sequence: {str(e)}",
                },
                status=400,
            )

        sequence = WaveformSequence.objects.create(
            name=name,
            description=description,
            sequence_data=varying_seq.description,
            total_duration=(
                varying_seq.duration if hasattr(varying_seq, "duration") else 0
            ),
            num_positions=total_elements,
        )

        created_elements = []
        for position in range(1, total_elements + 1):
            elem = varying_seq.element(position)

            position_element = WaveformElement.objects.create(
                name=f"{name}_pos{position}",
                description=f"Parametric element {position}/{total_elements} from '{name}'",
                element_data=elem.description,
                sample_rate=base_element_model.sample_rate,
                duration=elem.duration,
                num_channels=base_element_model.num_channels,
                is_auto_generated=True,
            )
            created_elements.append(position_element)

        for position, position_element in enumerate(created_elements, start=1):
            goto_position = 1 if position == total_elements else None

            SequenceElement.objects.create(
                sequence=sequence,
                waveform_element=position_element,
                position=position,
                trigger_input=trigger_input,
                repetitions=repetitions,
                goto_position=goto_position,
                flags=flags,
            )

        sequence_elements = [
            {
                "element_id": seq_elem.waveform_element.id,
                "position": seq_elem.position,
                "trigger_input": seq_elem.trigger_input,
                "repetitions": seq_elem.repetitions,
                "goto": seq_elem.goto_position,
                "flags": seq_elem.flags,
            }
            for seq_elem in sequence.elements.all().order_by("position")
        ]

        seq_with_settings, _, _ = _build_sequence(sequence_elements)

        sequence.sequence_data = seq_with_settings.description
        sequence.save()

        return JsonResponse(
            {
                "success": True,
                "message": "Parametric sequence generated successfully",
                "sequence_id": sequence.pk,
                "sequence_name": sequence.name,
                "num_elements": total_elements,
            }
        )

    except WaveformElement.DoesNotExist:
        return JsonResponse(
            {"success": False, "error": "Base element not found"}, status=404
        )
    except Exception as e:
        import traceback

        traceback.print_exc()
        return JsonResponse({"success": False, "error": str(e)}, status=400)

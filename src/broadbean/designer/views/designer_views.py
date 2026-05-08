"""Views for the waveform designer interface (designer.html)."""

import json
import os
import tempfile

import numpy as np
import plotly.utils
from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from broadbean.element import ElementDurationError
from broadbean.plotting import plotter

from ..models import WaveformElement
from ..utils import parse_element_data_to_ui_format
from .common import _build_element


def designer_view(request):
    """Main designer interface view."""
    context = {
        "default_sample_rate": settings.WAVEFORM_DESIGNER_DEFAULT_SAMPLE_RATE,
    }
    return render(request, "waveform_designer/designer.html", context)


def get_segment_types(request):
    """Return available waveform segment types."""
    segment_types = [
        {
            "id": "ramp",
            "name": "Ramp",
            "description": "Linear rise or fall",
            "color": "#3498db",
            "parameters": ["duration", "start", "stop"],
        },
        {
            "id": "sine",
            "name": "Sine Wave",
            "description": "Sinusoidal waveform",
            "color": "#e74c3c",
            "parameters": ["amplitude", "frequency", "phase", "offset", "duration"],
        },
        {
            "id": "gaussian",
            "name": "Gaussian",
            "description": "Gaussian pulse",
            "color": "#9b59b6",
            "parameters": ["amplitude", "width", "center", "offset", "duration"],
        },
        {
            "id": "exponential",
            "name": "Exponential",
            "description": "Exponential decay/rise",
            "color": "#2ecc71",
            "parameters": ["amplitude", "time_constant", "type", "duration"],
        },
        {
            "id": "waituntil",
            "name": "Wait Until",
            "description": "Wait until absolute time",
            "color": "#f39c12",
            "parameters": ["absolute_time"],
        },
        {
            "id": "custom",
            "name": "Custom",
            "description": "User-defined waveform",
            "color": "#34495e",
            "parameters": ["duration", "expression", "parameters"],
        },
    ]
    return JsonResponse({"segments": segment_types})


@csrf_exempt
@require_http_methods(["POST"])
def export_waveform(request):
    """Export waveform configuration as broadbean JSON."""
    try:
        data = json.loads(request.body)

        channels = data.get("channels", [])
        sample_rate = data.get(
            "sample_rate", settings.WAVEFORM_DESIGNER_DEFAULT_SAMPLE_RATE
        )
        filename = data.get("filename", "waveform_design")

        elem = _build_element(channels, sample_rate)

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as tmp_file:
            tmp_path = tmp_file.name

        try:
            elem.write_to_json(tmp_path)

            with open(tmp_path) as f:
                json_content = f.read()

            response = HttpResponse(json_content, content_type="application/json")
            response["Content-Disposition"] = f'attachment; filename="{filename}.json"'
            return response

        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    except Exception as e:
        import traceback

        traceback.print_exc()
        return JsonResponse({"success": False, "error": str(e)}, status=400)


@csrf_exempt
@require_http_methods(["POST"])
def preview_waveform(request):
    """Generate preview data for the current waveform configuration."""
    try:
        data = json.loads(request.body)

        channels = data.get("channels", [])
        sample_rate = data.get(
            "sample_rate", settings.WAVEFORM_DESIGNER_DEFAULT_SAMPLE_RATE
        )

        elem = _build_element(channels, sample_rate)

        try:
            fig = plotter(elem, backend="plotly")
        except ElementDurationError as e:
            error_msg = str(e)
            channel_info = []

            if "(Channel, npts):" in error_msg:
                import re

                matches = re.findall(r"\((\d+),\s*(\d+)\)", error_msg)
                channel_info = [
                    {"channel": int(ch), "npts": int(pts)} for ch, pts in matches
                ]

            return JsonResponse(
                {
                    "success": False,
                    "error_type": "duration_mismatch",
                    "error_message": "All channels within the waveform element must be the same length.",
                    "channel_info": channel_info,
                },
                status=400,
            )

        total_duration = elem.duration if hasattr(elem, "duration") else 0
        total_points = elem.points if hasattr(elem, "points") else 0

        peak_amplitude = 0
        for channel_idx in range(len(channels)):
            arrays_dict = elem.getArrays()
            channel_key = channel_idx + 1

            if channel_key in arrays_dict:
                bp_data = arrays_dict[channel_key]
                if isinstance(bp_data, dict):
                    if "waveform" in bp_data:
                        waveform_data = bp_data["waveform"]
                    else:
                        waveform_data = next(iter(bp_data.values()))
                else:
                    waveform_data = bp_data

                if len(waveform_data) > 0:
                    peak_amplitude = max(
                        peak_amplitude, float(np.max(np.abs(waveform_data)))
                    )

        plot_json = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)

        return JsonResponse(
            {
                "success": True,
                "plot": plot_json,
                "stats": {
                    "total_duration": total_duration,
                    "sample_rate": sample_rate,
                    "points": total_points,
                    "peak_amplitude": peak_amplitude,
                },
            }
        )

    except Exception as e:
        import traceback

        traceback.print_exc()
        return JsonResponse({"success": False, "error": str(e)}, status=400)


@csrf_exempt
@require_http_methods(["POST"])
def save_waveform_element(request):
    """Save a waveform element to the database."""
    try:
        data = json.loads(request.body)

        name = data.get("name", "Untitled Element")
        description = data.get("description", "")
        channels = data.get("channels", [])
        sample_rate = data.get(
            "sample_rate", settings.WAVEFORM_DESIGNER_DEFAULT_SAMPLE_RATE
        )

        if not channels or not any(ch.get("segments") for ch in channels):
            return JsonResponse(
                {"success": False, "error": "No waveform data to save"}, status=400
            )

        elem = _build_element(channels, sample_rate)

        waveform_element = WaveformElement.objects.create(
            name=name,
            description=description,
            element_data=elem.description,
            sample_rate=sample_rate,
            duration=elem.duration,
            num_channels=len(channels),
        )

        return JsonResponse(
            {
                "success": True,
                "message": "Waveform element saved successfully",
                "element_id": waveform_element.pk,
                "name": waveform_element.name,
            }
        )

    except Exception as e:
        import traceback

        traceback.print_exc()
        return JsonResponse({"success": False, "error": str(e)}, status=400)


@csrf_exempt
@require_http_methods(["PUT"])
def update_waveform_element(request, element_id):
    """Update an existing waveform element."""
    try:
        data = json.loads(request.body)

        name = data.get("name", "Untitled Element")
        description = data.get("description", "")
        channels = data.get("channels", [])
        sample_rate = data.get(
            "sample_rate", settings.WAVEFORM_DESIGNER_DEFAULT_SAMPLE_RATE
        )

        if not channels or not any(ch.get("segments") for ch in channels):
            return JsonResponse(
                {"success": False, "error": "No waveform data to save"}, status=400
            )

        try:
            waveform_element = WaveformElement.objects.get(id=element_id)
        except WaveformElement.DoesNotExist:
            return JsonResponse(
                {"success": False, "error": "Element not found"}, status=404
            )

        elem = _build_element(channels, sample_rate)

        waveform_element.name = name
        waveform_element.description = description
        waveform_element.element_data = elem.description
        waveform_element.sample_rate = sample_rate
        waveform_element.duration = elem.duration
        waveform_element.num_channels = len(channels)
        waveform_element.save()

        return JsonResponse(
            {
                "success": True,
                "message": "Waveform element updated successfully",
                "element_id": waveform_element.pk,
                "name": waveform_element.name,
            }
        )

    except Exception as e:
        import traceback

        traceback.print_exc()
        return JsonResponse({"success": False, "error": str(e)}, status=400)


@csrf_exempt
@require_http_methods(["DELETE"])
def delete_waveform_element(request, element_id):
    """Delete a waveform element from the database."""
    try:
        try:
            waveform_element = WaveformElement.objects.get(id=element_id)
        except WaveformElement.DoesNotExist:
            return JsonResponse(
                {"success": False, "error": "Element not found"}, status=404
            )

        element_name = waveform_element.name
        waveform_element.delete()

        return JsonResponse(
            {
                "success": True,
                "message": f"Element '{element_name}' deleted successfully",
            }
        )

    except Exception as e:
        import traceback

        traceback.print_exc()
        return JsonResponse({"success": False, "error": str(e)}, status=400)


@require_http_methods(["GET"])
def get_waveform_elements(request):
    """Get list of all saved waveform elements."""
    try:
        elements = WaveformElement.objects.filter(is_auto_generated=False)

        elements_data = [
            {
                "id": elem.pk,
                "name": elem.name,
                "description": elem.description,
                "duration": elem.duration,
                "num_channels": elem.num_channels,
                "sample_rate": elem.sample_rate,
                "channels": parse_element_data_to_ui_format(elem.element_data),
                "created_at": elem.created_at.isoformat(),
            }
            for elem in elements
        ]

        return JsonResponse({"success": True, "elements": elements_data})

    except Exception as e:
        import traceback

        traceback.print_exc()
        return JsonResponse({"success": False, "error": str(e)}, status=400)


@require_http_methods(["GET"])
def get_waveform_element(request, element_id):
    """Get details of a specific waveform element."""
    try:
        element = WaveformElement.objects.get(id=element_id)

        return JsonResponse(
            {
                "success": True,
                "element": {
                    "id": element.pk,
                    "name": element.name,
                    "description": element.description,
                    "element_data": element.element_data,
                    "channels": parse_element_data_to_ui_format(element.element_data),
                    "duration": element.duration,
                    "num_channels": element.num_channels,
                    "sample_rate": element.sample_rate,
                    "created_at": element.created_at.isoformat(),
                },
            }
        )

    except WaveformElement.DoesNotExist:
        return JsonResponse(
            {"success": False, "error": "Element not found"}, status=404
        )
    except Exception as e:
        import traceback

        traceback.print_exc()
        return JsonResponse({"success": False, "error": str(e)}, status=400)

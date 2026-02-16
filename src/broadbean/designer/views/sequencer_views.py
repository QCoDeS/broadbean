"""Views for the sequencer interface (sequencer.html)."""

import json

import plotly.utils
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from broadbean.element import ElementDurationError
from broadbean.plotting import plotter
from broadbean.sequence import Sequence

from ..models import SequenceElement, WaveformElement, WaveformSequence
from .common import _build_sequence


def sequencer_view(request):
    """Main sequencer interface view."""
    return render(request, "waveform_designer/sequencer.html")


@csrf_exempt
@require_http_methods(["POST"])
def preview_sequence(request):
    """Generate preview for a waveform sequence."""
    try:
        data = json.loads(request.body)

        sequence_elements = data.get("elements", [])
        max_subsequences = data.get("max_subsequences", 10)

        if not sequence_elements:
            return JsonResponse(
                {"success": False, "error": "No elements in sequence"}, status=400
            )

        seq, sample_rate, total_duration = _build_sequence(sequence_elements)
        num_positions = len(sequence_elements)

        try:
            fig = plotter(seq, backend="plotly", max_subsequences=max_subsequences)

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

        plot_json = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)

        # Include display info for the frontend to show
        display_info = None
        if num_positions > max_subsequences:
            display_info = f"Sequences 1-{max_subsequences} of {num_positions} shown"

        return JsonResponse(
            {
                "success": True,
                "plot": plot_json,
                "display_info": display_info,
                "stats": {
                    "num_positions": len(sequence_elements),
                    "total_duration": total_duration,
                    "sample_rate": sample_rate,
                },
            }
        )

    except Exception as e:
        import traceback

        traceback.print_exc()
        return JsonResponse({"success": False, "error": str(e)}, status=400)


@csrf_exempt
@require_http_methods(["POST"])
def save_sequence(request):
    """Save a waveform sequence to the database."""
    try:
        data = json.loads(request.body)

        name = data.get("name", "Untitled Sequence")
        description = data.get("description", "")
        sequence_elements = data.get("elements", [])

        if not sequence_elements:
            return JsonResponse(
                {"success": False, "error": "No elements in sequence"}, status=400
            )

        seq, sample_rate, total_duration = _build_sequence(sequence_elements)

        sequence = WaveformSequence.objects.create(
            name=name,
            description=description,
            sequence_data=seq.description,
            total_duration=total_duration,
            num_positions=len(sequence_elements),
        )

        for seq_elem_data in sequence_elements:
            element_id = seq_elem_data.get("element_id")
            position = seq_elem_data.get("position")
            trigger_input = seq_elem_data.get("trigger_input", 0)
            repetitions = seq_elem_data.get("repetitions", 1)
            goto = seq_elem_data.get("goto")
            flags = seq_elem_data.get("flags")

            elem_model = WaveformElement.objects.get(id=element_id)

            SequenceElement.objects.create(
                sequence=sequence,
                waveform_element=elem_model,
                position=position,
                trigger_input=trigger_input,
                repetitions=repetitions,
                goto_position=goto,
                flags=flags,
            )

        return JsonResponse(
            {
                "success": True,
                "message": "Sequence saved successfully",
                "sequence_id": sequence.id,
                "name": sequence.name,
            }
        )

    except Exception as e:
        import traceback

        traceback.print_exc()
        return JsonResponse({"success": False, "error": str(e)}, status=400)


@require_http_methods(["GET"])
def get_sequences(request):
    """Get list of all saved waveform sequences."""
    try:
        sequences = WaveformSequence.objects.all()

        sequences_data = [
            {
                "id": seq.id,
                "name": seq.name,
                "description": seq.description,
                "total_duration": seq.total_duration,
                "num_positions": seq.num_positions,
                "created_at": seq.created_at.isoformat(),
            }
            for seq in sequences
        ]

        return JsonResponse({"success": True, "sequences": sequences_data})

    except Exception as e:
        import traceback

        traceback.print_exc()
        return JsonResponse({"success": False, "error": str(e)}, status=400)


@csrf_exempt
@require_http_methods(["GET", "PUT"])
def sequence_detail_update(request, sequence_id):
    """Handle both GET and PUT for sequence detail/update operations."""
    if request.method == "GET":
        return get_sequence_detail(request, sequence_id)
    elif request.method == "PUT":
        return update_sequence(request, sequence_id)


def get_sequence_detail(request, sequence_id):
    """Get details of a specific waveform sequence including element data."""
    try:
        sequence = WaveformSequence.objects.get(id=sequence_id)

        sequence_elements = sequence.elements.all().order_by("position")

        elements_data = [
            {
                "element_id": seq_elem.waveform_element.id,
                "element_name": seq_elem.waveform_element.name,
                "position": seq_elem.position,
                "trigger_input": seq_elem.trigger_input,
                "repetitions": seq_elem.repetitions,
                "goto_position": seq_elem.goto_position,
                "flags": seq_elem.flags,
            }
            for seq_elem in sequence_elements
        ]

        return JsonResponse(
            {
                "success": True,
                "sequence": {
                    "id": sequence.id,
                    "name": sequence.name,
                    "description": sequence.description,
                    "sequence_data": sequence.sequence_data,
                    "elements": elements_data,
                    "total_duration": sequence.total_duration,
                    "num_positions": sequence.num_positions,
                    "created_at": sequence.created_at.isoformat(),
                },
            }
        )

    except WaveformSequence.DoesNotExist:
        return JsonResponse(
            {"success": False, "error": "Sequence not found"}, status=404
        )
    except Exception as e:
        import traceback

        traceback.print_exc()
        return JsonResponse({"success": False, "error": str(e)}, status=400)


@csrf_exempt
@require_http_methods(["PUT"])
def update_sequence(request, sequence_id):
    """Update an existing waveform sequence."""
    try:
        data = json.loads(request.body)

        name = data.get("name", "Untitled Sequence")
        description = data.get("description", "")
        sequence_elements = data.get("elements", [])

        if not sequence_elements:
            return JsonResponse(
                {"success": False, "error": "No elements in sequence"}, status=400
            )

        try:
            sequence = WaveformSequence.objects.get(id=sequence_id)
        except WaveformSequence.DoesNotExist:
            return JsonResponse(
                {"success": False, "error": "Sequence not found"}, status=404
            )

        seq, sample_rate, total_duration = _build_sequence(sequence_elements)

        sequence.name = name
        sequence.description = description
        sequence.sequence_data = seq.description
        sequence.total_duration = total_duration
        sequence.num_positions = len(sequence_elements)
        sequence.save()

        sequence.elements.all().delete()

        for seq_elem_data in sequence_elements:
            element_id = seq_elem_data.get("element_id")
            position = seq_elem_data.get("position")
            trigger_input = seq_elem_data.get("trigger_input", 0)
            repetitions = seq_elem_data.get("repetitions", 1)
            goto = seq_elem_data.get("goto")
            flags = seq_elem_data.get("flags")

            elem_model = WaveformElement.objects.get(id=element_id)

            SequenceElement.objects.create(
                sequence=sequence,
                waveform_element=elem_model,
                position=position,
                trigger_input=trigger_input,
                repetitions=repetitions,
                goto_position=goto,
                flags=flags,
            )

        return JsonResponse(
            {
                "success": True,
                "message": "Sequence updated successfully",
                "sequence_id": sequence.id,
                "name": sequence.name,
            }
        )

    except Exception as e:
        import traceback

        traceback.print_exc()
        return JsonResponse({"success": False, "error": str(e)}, status=400)


@require_http_methods(["GET"])
def download_sequence_data(request, sequence_id):
    """Download sequence_data as JSON file."""
    try:
        sequence = WaveformSequence.objects.get(id=sequence_id)

        # Convert to JSON string with nice formatting
        json_content = json.dumps(sequence.sequence_data, indent=2)
        filename = f"{sequence.name.replace(' ', '_')}_sequence_data.json"

        # Create HTTP response with JSON content
        response = HttpResponse(json_content, content_type="application/json")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'

        return response

    except WaveformSequence.DoesNotExist:
        return JsonResponse(
            {"success": False, "error": "Sequence not found"}, status=404
        )
    except Exception as e:
        import traceback

        traceback.print_exc()
        return JsonResponse({"success": False, "error": str(e)}, status=400)


@csrf_exempt
@require_http_methods(["DELETE"])
def delete_sequence(request, sequence_id):
    """Delete a waveform sequence from the database."""
    try:
        try:
            sequence = WaveformSequence.objects.get(id=sequence_id)
        except WaveformSequence.DoesNotExist:
            return JsonResponse(
                {"success": False, "error": "Sequence not found"}, status=404
            )

        sequence_name = sequence.name
        sequence.delete()

        return JsonResponse(
            {
                "success": True,
                "message": f"Sequence '{sequence_name}' deleted successfully",
            }
        )

    except Exception as e:
        import traceback

        traceback.print_exc()
        return JsonResponse({"success": False, "error": str(e)}, status=400)


@require_http_methods(["GET"])
def get_sequence_channels(request, sequence_id):
    """Get channel information for a specific sequence."""
    try:
        sequence_model = WaveformSequence.objects.get(id=sequence_id)
        seq = Sequence.sequence_from_description(sequence_model.sequence_data)
        channels_data = [{"number": channel} for channel in sorted(seq.channels)]

        return JsonResponse({"success": True, "channels": channels_data})

    except WaveformSequence.DoesNotExist:
        return JsonResponse(
            {"success": False, "error": "Sequence not found"}, status=404
        )
    except Exception as e:
        import traceback

        traceback.print_exc()
        return JsonResponse({"success": False, "error": str(e)}, status=400)


@require_http_methods(["GET"])
def preview_saved_sequence(request, sequence_id):
    """Generate preview for a saved waveform sequence."""
    try:
        # Get max_subsequences from query parameter, default to 10
        max_subsequences = int(request.GET.get("max_subsequences", 10))

        sequence_model = WaveformSequence.objects.get(id=sequence_id)
        seq = Sequence.sequence_from_description(sequence_model.sequence_data)
        num_positions = sequence_model.num_positions

        try:
            fig = plotter(seq, backend="plotly", max_subsequences=max_subsequences)

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

        plot_json = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)

        # Include display info for the frontend to show
        display_info = None
        if num_positions > max_subsequences:
            display_info = f"Sequences 1-{max_subsequences} of {num_positions} shown"

        return JsonResponse(
            {
                "success": True,
                "plot": plot_json,
                "display_info": display_info,
                "stats": {
                    "num_positions": sequence_model.num_positions,
                    "total_duration": sequence_model.total_duration,
                    "sample_rate": seq.SR if hasattr(seq, "SR") else 0,
                },
            }
        )

    except WaveformSequence.DoesNotExist:
        return JsonResponse(
            {"success": False, "error": "Sequence not found"}, status=404
        )
    except Exception as e:
        import traceback

        traceback.print_exc()
        return JsonResponse({"success": False, "error": str(e)}, status=400)

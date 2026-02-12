"""Views for the upload & capture interface (upload.html)."""

import json
import logging
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from ..models import AWGStationConfig, ScopeStationConfig, WaveformSequence, LUTConfig
from broadbean.instruments.base.mock_state import mock_state
from .common import _get_instruments, reset_instrument_instances

logger = logging.getLogger(__name__)


def upload_view(request):
    """Waveform upload & capture interface view."""
    return render(request, "waveform_designer/upload.html")


@csrf_exempt
@require_http_methods(["POST"])
def upload_sequence(request):
    """Upload sequence to AWG (mock or real hardware based on config).

    Request body should include:
        - sequence_id: ID of the WaveformSequence to upload
        - awg_config_id: ID of the AWGConfig to use
        - scope_config_id: ID of the ScopeConfig to use
        - lut_channel_1_id: Optional ID of LUTConfig for channel 1
        - lut_channel_2_id: Optional ID of LUTConfig for channel 2
    """
    try:
        data = json.loads(request.body)

        sequence_id = data.get("sequence_id")
        awg_config_id = data.get("awg_config_id")
        scope_config_id = data.get("scope_config_id")
        lut_channel_1_id = data.get("lut_channel_1_id")  # Optional
        lut_channel_2_id = data.get("lut_channel_2_id")  # Optional

        if not sequence_id:
            return JsonResponse(
                {"success": False, "error": "sequence_id is required"},
                status=400,
            )

        if not awg_config_id:
            return JsonResponse(
                {"success": False, "error": "awg_config_id is required"},
                status=400,
            )

        if not scope_config_id:
            return JsonResponse(
                {"success": False, "error": "scope_config_id is required"},
                status=400,
            )

        # Load sequence from database
        sequence_model = WaveformSequence.objects.get(id=sequence_id)

        # Get instruments based on configurations (mock or real hardware)
        awg, scope = _get_instruments(awg_config_id, scope_config_id)

        # Store in mock_state for later retrieval
        mock_state.set_instruments(awg, scope)

        # Build calibration from LUT configs if provided
        calibration = None
        if lut_channel_1_id or lut_channel_2_id:
            calibration = {}

            if lut_channel_1_id:
                lut_1 = LUTConfig.objects.get(id=lut_channel_1_id)
                calibration[1] = {
                    "channel_number": 1,
                    "input_lut": lut_1.input_lut,
                    "output_lut": lut_1.output_lut,
                }

            if lut_channel_2_id:
                lut_2 = LUTConfig.objects.get(id=lut_channel_2_id)
                calibration[2] = {
                    "channel_number": 2,
                    "input_lut": lut_2.input_lut,
                    "output_lut": lut_2.output_lut,
                }

        # Upload sequence to AWG using upload_sequence which applies LUT calibration
        awg.upload_sequence(
            sequence_model.sequence_data, sequence_model.name, calibration
        )

        # Determine if using mock or real hardware for logging
        awg_config_model = AWGStationConfig.objects.get(id=awg_config_id)
        is_mock = awg_config_model.is_mock
        mode_str = "mock" if is_mock else "real"
        logger.info(f"Sequence '{sequence_model.name}' uploaded to {mode_str} AWG")

        return JsonResponse(
            {
                "success": True,
                "message": f"Sequence '{sequence_model.name}' uploaded to AWG successfully",
                "is_mock": is_mock,
            }
        )

    except WaveformSequence.DoesNotExist:
        return JsonResponse(
            {"success": False, "error": "Sequence not found"}, status=404
        )
    except AWGStationConfig.DoesNotExist:
        return JsonResponse(
            {"success": False, "error": "AWG configuration not found"},
            status=404,
        )
    except ScopeStationConfig.DoesNotExist:
        return JsonResponse(
            {"success": False, "error": "Scope configuration not found"},
            status=404,
        )
    except LUTConfig.DoesNotExist:
        return JsonResponse(
            {"success": False, "error": "LUT configuration not found"},
            status=404,
        )
    except Exception as e:
        import traceback

        traceback.print_exc()
        return JsonResponse({"success": False, "error": str(e)}, status=400)


@csrf_exempt
@require_http_methods(["POST"])
def trigger_and_capture(request):
    """Trigger AWG and capture from scope."""
    try:
        if not mock_state.has_instruments():
            return JsonResponse(
                {
                    "success": False,
                    "error": "No instruments available. Please upload a sequence first.",
                },
                status=400,
            )

        awg, scope = mock_state.get_instruments()

        try:
            # Arm scope
            scope.single()
            logger.debug("Scope armed and waiting for trigger")

            # Trigger AWG
            awg.trigger()
            logger.debug("AWG triggered")

            # Download waveforms
            waveforms = scope.download()
            logger.info("Waveforms downloaded from scope")

            # Get timebase
            time_unit, time_axis = scope.timebase()

            # Prepare channel data
            channels_data = []
            for idx, waveform in enumerate(waveforms):
                channels_data.append(
                    {
                        "name": f"CH{idx + 1}",
                        "data": waveform.tolist(),
                    }
                )

            return JsonResponse(
                {
                    "success": True,
                    "message": "AWG triggered and waveforms captured successfully",
                    "time_axis": time_axis.tolist(),
                    "time_unit": time_unit,
                    "channels": channels_data,
                }
            )

        except Exception as e:
            import traceback

            traceback.print_exc()
            return JsonResponse({"success": False, "error": str(e)}, status=400)

    except Exception as e:
        import traceback

        traceback.print_exc()
        return JsonResponse({"success": False, "error": str(e)}, status=400)


@csrf_exempt
@require_http_methods(["POST"])
def jump_to_and_capture(request):
    """Jump to specific segment on AWG and capture from scope."""
    try:
        data = json.loads(request.body)

        segment_index = data.get("segment_index")

        if not segment_index:
            return JsonResponse(
                {"success": False, "error": "segment_index is required"},
                status=400,
            )

        if not mock_state.has_instruments():
            return JsonResponse(
                {
                    "success": False,
                    "error": "No instruments available. Please upload a sequence first.",
                },
                status=400,
            )

        awg, scope = mock_state.get_instruments()

        try:
            # Arm scope
            scope.single()
            logger.info("Scope armed and waiting for trigger")

            # Jump to segment and trigger
            awg.jump_to(segment_index)
            logger.info(f"AWG jumped to segment {segment_index}")
            awg.trigger()
            logger.debug("AWG triggered")

            # Download waveforms
            waveforms = scope.download()
            logger.info("Waveforms downloaded from scope")

            # Get timebase
            time_unit, time_axis = scope.timebase()

            # Prepare channel data
            channels_data = []
            for idx, waveform in enumerate(waveforms):
                channels_data.append(
                    {
                        "name": f"CH{idx + 1}",
                        "data": waveform.tolist(),
                    }
                )

            return JsonResponse(
                {
                    "success": True,
                    "message": f"AWG jumped to segment {segment_index} and waveforms captured",
                    "time_axis": time_axis.tolist(),
                    "time_unit": time_unit,
                    "channels": channels_data,
                    "segment_index": segment_index,
                }
            )

        except Exception as e:
            import traceback

            traceback.print_exc()
            return JsonResponse({"success": False, "error": str(e)}, status=400)

    except Exception as e:
        import traceback

        traceback.print_exc()
        return JsonResponse({"success": False, "error": str(e)}, status=400)


@csrf_exempt
@require_http_methods(["POST"])
def disconnect_instruments(request):
    """Disconnect AWG and Scope instruments."""
    try:
        mock_state.disconnect_instruments()
        mock_state.reset()

        reset_instrument_instances()

        return JsonResponse(
            {
                "success": True,
                "message": "Instruments disconnected successfully",
            }
        )

    except Exception as e:
        import traceback

        traceback.print_exc()
        return JsonResponse({"success": False, "error": str(e)}, status=400)

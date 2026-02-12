"""Views for instrument configuration interface (instruments.html)."""

import csv
import io
import json
import logging
from django.shortcuts import render
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from ..models import (
    AWGStationConfig,
    ScopeStationConfig,
    LUTConfig,
    AWG_DRIVER_MOCK,
    SCOPE_DRIVER_MOCK,
    AWG_DRIVER_CHOICES,
    SCOPE_DRIVER_CHOICES,
)

# Import factories for instrument configuration
from broadbean.interface.awg import AWGFactory
from broadbean.interface.scope import ScopeFactory

logger = logging.getLogger(__name__)


def instruments_view(request):
    """Instrument configuration interface view."""
    return render(request, "waveform_designer/instruments.html")


@require_http_methods(["GET"])
def get_instrument_types(request):
    """Return available instrument types for AWG and Scope."""
    # Build AWG types list with display names
    awg_types = []
    for driver_value, driver_label in AWG_DRIVER_CHOICES:
        awg_types.append(
            {
                "value": driver_value,
                "label": driver_label,
                "is_mock": driver_value == AWG_DRIVER_MOCK,
            }
        )

    # Build Scope types list with display names
    scope_types = []
    for driver_value, driver_label in SCOPE_DRIVER_CHOICES:
        scope_types.append(
            {
                "value": driver_value,
                "label": driver_label,
                "is_mock": driver_value == SCOPE_DRIVER_MOCK,
            }
        )

    return JsonResponse(
        {
            "success": True,
            "awg_types": awg_types,
            "scope_types": scope_types,
        }
    )


# ============================================================================
# AWG CONFIG API
# ============================================================================


@require_http_methods(["GET"])
def get_awg_configs(request):
    """Get list of all saved AWG configurations."""
    try:
        configs = AWGStationConfig.objects.all()

        configs_data = [
            {
                "id": config.id,
                "name": config.name,
                "description": config.description,
                "is_mock": config.is_mock,
                "address": config.address,
                "driver_type": config.driver_type,
                "parameters": config.parameters,
                "use_flags": config.use_flags,
                "created_at": config.created_at.isoformat(),
            }
            for config in configs
        ]

        return JsonResponse({"success": True, "configs": configs_data})

    except Exception as e:
        import traceback

        traceback.print_exc()
        return JsonResponse({"success": False, "error": str(e)}, status=400)


@csrf_exempt
@require_http_methods(["GET", "POST"])
def awg_config_list_create(request):
    """Handle GET (list) and POST (create) for AWG configs."""
    if request.method == "GET":
        return get_awg_configs(request)
    elif request.method == "POST":
        return create_awg_config(request)


def create_awg_config(request):
    """Create a new AWG configuration."""
    try:
        data = json.loads(request.body)

        name = data.get("name", "").strip()
        description = data.get("description", "")

        # Frontend now sends driver_type directly
        driver_type = data.get("driver_type", AWG_DRIVER_MOCK)
        address = data.get("address", "TCPIP0::192.168.0.2::inst0::INSTR")
        parameters = data.get("parameters", {})
        use_flags = data.get("use_flags", False)
        yaml_content = data.get("yaml_content", "")

        if not name:
            return JsonResponse(
                {"success": False, "error": "Configuration name is required"},
                status=400,
            )

        # Check for duplicate name
        if AWGStationConfig.objects.filter(name=name).exists():
            return JsonResponse(
                {
                    "success": False,
                    "error": f"An AWG configuration named '{name}' already exists",
                },
                status=400,
            )

        awg_config = AWGStationConfig.objects.create(
            name=name,
            description=description,
            address=address,
            driver_type=driver_type,
            parameters=parameters,
            use_flags=use_flags,
            yaml_content=yaml_content,
        )

        return JsonResponse(
            {
                "success": True,
                "message": "AWG configuration created successfully",
                "config": {
                    "id": awg_config.id,
                    "name": awg_config.name,
                    "description": awg_config.description,
                    "is_mock": awg_config.is_mock,
                    "address": awg_config.address,
                    "driver_type": awg_config.driver_type,
                    "parameters": awg_config.parameters,
                    "use_flags": awg_config.use_flags,
                },
            }
        )

    except Exception as e:
        import traceback

        traceback.print_exc()
        return JsonResponse({"success": False, "error": str(e)}, status=400)


@csrf_exempt
@require_http_methods(["GET", "PUT", "DELETE"])
def awg_config_detail(request, config_id):
    """Handle GET, PUT, DELETE for a specific AWG config."""
    if request.method == "GET":
        return get_awg_config_detail(request, config_id)
    elif request.method == "PUT":
        return update_awg_config(request, config_id)
    elif request.method == "DELETE":
        return delete_awg_config(request, config_id)


def get_awg_config_detail(request, config_id):
    """Get details of a specific AWG configuration."""
    try:
        config = AWGStationConfig.objects.get(id=config_id)

        return JsonResponse(
            {
                "success": True,
                "config": {
                    "id": config.id,
                    "name": config.name,
                    "description": config.description,
                    "is_mock": config.is_mock,
                    "address": config.address,
                    "driver_type": config.driver_type,
                    "parameters": config.parameters,
                    "use_flags": config.use_flags,
                    "created_at": config.created_at.isoformat(),
                },
            }
        )

    except AWGStationConfig.DoesNotExist:
        return JsonResponse(
            {"success": False, "error": "AWG configuration not found"}, status=404
        )
    except Exception as e:
        import traceback

        traceback.print_exc()
        return JsonResponse({"success": False, "error": str(e)}, status=400)


def update_awg_config(request, config_id):
    """Update an existing AWG configuration."""
    try:
        data = json.loads(request.body)

        try:
            awg_config = AWGStationConfig.objects.get(id=config_id)
        except AWGStationConfig.DoesNotExist:
            return JsonResponse(
                {"success": False, "error": "AWG configuration not found"}, status=404
            )

        # Get config data - support both old format (nested 'config') and new flat format
        config_data = data.get("config", data)

        name = data.get("name", awg_config.name).strip()
        description = data.get("description", awg_config.description)
        address = config_data.get("address", awg_config.address)
        driver_type = config_data.get("driver_type", awg_config.driver_type)
        parameters = config_data.get("parameters", awg_config.parameters)
        use_flags = config_data.get("use_flags", awg_config.use_flags)
        yaml_content = config_data.get("yaml_content", awg_config.yaml_content)

        if not name:
            return JsonResponse(
                {"success": False, "error": "Configuration name is required"},
                status=400,
            )

        # Check for duplicate name (excluding current config)
        if AWGStationConfig.objects.filter(name=name).exclude(id=config_id).exists():
            return JsonResponse(
                {
                    "success": False,
                    "error": f"An AWG configuration named '{name}' already exists",
                },
                status=400,
            )

        awg_config.name = name
        awg_config.description = description
        awg_config.address = address
        awg_config.driver_type = driver_type
        awg_config.parameters = parameters
        awg_config.use_flags = use_flags
        awg_config.yaml_content = yaml_content
        awg_config.save()

        return JsonResponse(
            {
                "success": True,
                "message": "AWG configuration updated successfully",
                "config": {
                    "id": awg_config.id,
                    "name": awg_config.name,
                    "description": awg_config.description,
                    "is_mock": awg_config.is_mock,
                    "address": awg_config.address,
                    "driver_type": awg_config.driver_type,
                    "parameters": awg_config.parameters,
                    "use_flags": awg_config.use_flags,
                },
            }
        )

    except Exception as e:
        import traceback

        traceback.print_exc()
        return JsonResponse({"success": False, "error": str(e)}, status=400)


def delete_awg_config(request, config_id):
    """Delete an AWG configuration."""
    try:
        try:
            config = AWGStationConfig.objects.get(id=config_id)
        except AWGStationConfig.DoesNotExist:
            return JsonResponse(
                {"success": False, "error": "AWG configuration not found"}, status=404
            )

        config_name = config.name
        config.delete()

        return JsonResponse(
            {
                "success": True,
                "message": f"AWG configuration '{config_name}' deleted successfully",
            }
        )

    except Exception as e:
        import traceback

        traceback.print_exc()
        return JsonResponse({"success": False, "error": str(e)}, status=400)


@require_http_methods(["GET"])
def download_awg_config(request, config_id):
    """Download AWG configuration as YAML file."""
    try:
        config = AWGStationConfig.objects.get(id=config_id)
        filename = f"{config.name.replace(' ', '_')}_awg.station.yaml"

        # Use the model's to_station_yaml method to generate YAML
        yaml_content = config.to_station_yaml()

        # Create HTTP response with YAML content
        response = HttpResponse(yaml_content, content_type="application/x-yaml")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'

        return response

    except AWGStationConfig.DoesNotExist:
        return JsonResponse(
            {"success": False, "error": "AWG configuration not found"}, status=404
        )
    except Exception as e:
        import traceback

        traceback.print_exc()
        return JsonResponse({"success": False, "error": str(e)}, status=400)


# ============================================================================
# SCOPE CONFIG API
# ============================================================================


def _normalize_scope_parameters(parameters: dict) -> dict:
    """Normalize scope parameters to ensure qcodes compatibility.

    QCodes validators expect lowercase values for trigger.type (e.g., 'edge' not 'EDGE').
    """
    if parameters and "trigger.type" in parameters:
        trigger_config = parameters["trigger.type"]
        if isinstance(trigger_config, dict) and "initial_value" in trigger_config:
            trigger_val = trigger_config["initial_value"]
            if isinstance(trigger_val, str):
                parameters["trigger.type"]["initial_value"] = trigger_val.lower()
    return parameters


@require_http_methods(["GET"])
def get_scope_configs(request):
    """Get list of all saved Scope configurations."""
    try:
        configs = ScopeStationConfig.objects.all()

        configs_data = [
            {
                "id": config.id,
                "name": config.name,
                "description": config.description,
                "is_mock": config.is_mock,
                "address": config.address,
                "driver_type": config.driver_type,
                "parameters": config.parameters,
                "channels": config.channels,
                "created_at": config.created_at.isoformat(),
            }
            for config in configs
        ]

        return JsonResponse({"success": True, "configs": configs_data})

    except Exception as e:
        import traceback

        traceback.print_exc()
        return JsonResponse({"success": False, "error": str(e)}, status=400)


@csrf_exempt
@require_http_methods(["GET", "POST"])
def scope_config_list_create(request):
    """Handle GET (list) and POST (create) for Scope configs."""
    if request.method == "GET":
        return get_scope_configs(request)
    elif request.method == "POST":
        return create_scope_config(request)


def create_scope_config(request):
    """Create a new Scope configuration."""
    try:
        data = json.loads(request.body)

        name = data.get("name", "").strip()
        description = data.get("description", "")

        # Frontend now sends driver_type directly
        driver_type = data.get("driver_type", SCOPE_DRIVER_MOCK)
        address = data.get("address", "TCPIP0::192.168.0.3::inst0::INSTR")
        parameters = data.get("parameters", {})
        channels = data.get("channels", [])
        yaml_content = data.get("yaml_content", "")

        if not name:
            return JsonResponse(
                {"success": False, "error": "Configuration name is required"},
                status=400,
            )

        # Check for duplicate name
        if ScopeStationConfig.objects.filter(name=name).exists():
            return JsonResponse(
                {
                    "success": False,
                    "error": f"A Scope configuration named '{name}' already exists",
                },
                status=400,
            )

        # Normalize parameters to ensure qcodes compatibility
        parameters = _normalize_scope_parameters(parameters)

        scope_config = ScopeStationConfig.objects.create(
            name=name,
            description=description,
            address=address,
            driver_type=driver_type,
            parameters=parameters,
            channels=channels,
            yaml_content=yaml_content,
        )

        return JsonResponse(
            {
                "success": True,
                "message": "Scope configuration created successfully",
                "config": {
                    "id": scope_config.id,
                    "name": scope_config.name,
                    "description": scope_config.description,
                    "is_mock": scope_config.is_mock,
                    "address": scope_config.address,
                    "driver_type": scope_config.driver_type,
                    "parameters": scope_config.parameters,
                    "channels": scope_config.channels,
                },
            }
        )

    except Exception as e:
        import traceback

        traceback.print_exc()
        return JsonResponse({"success": False, "error": str(e)}, status=400)


@csrf_exempt
@require_http_methods(["GET", "PUT", "DELETE"])
def scope_config_detail(request, config_id):
    """Handle GET, PUT, DELETE for a specific Scope config."""
    if request.method == "GET":
        return get_scope_config_detail(request, config_id)
    elif request.method == "PUT":
        return update_scope_config(request, config_id)
    elif request.method == "DELETE":
        return delete_scope_config(request, config_id)


def get_scope_config_detail(request, config_id):
    """Get details of a specific Scope configuration."""
    try:
        config = ScopeStationConfig.objects.get(id=config_id)

        return JsonResponse(
            {
                "success": True,
                "config": {
                    "id": config.id,
                    "name": config.name,
                    "description": config.description,
                    "is_mock": config.is_mock,
                    "address": config.address,
                    "driver_type": config.driver_type,
                    "parameters": config.parameters,
                    "channels": config.channels,
                    "created_at": config.created_at.isoformat(),
                },
            }
        )

    except ScopeStationConfig.DoesNotExist:
        return JsonResponse(
            {"success": False, "error": "Scope configuration not found"}, status=404
        )
    except Exception as e:
        import traceback

        traceback.print_exc()
        return JsonResponse({"success": False, "error": str(e)}, status=400)


def update_scope_config(request, config_id):
    """Update an existing Scope configuration."""
    try:
        data = json.loads(request.body)

        try:
            scope_config = ScopeStationConfig.objects.get(id=config_id)
        except ScopeStationConfig.DoesNotExist:
            return JsonResponse(
                {"success": False, "error": "Scope configuration not found"}, status=404
            )

        # Get config data - support both old format (nested 'config') and new flat format
        config_data = data.get("config", data)

        name = data.get("name", scope_config.name).strip()
        description = data.get("description", scope_config.description)
        address = config_data.get("address", scope_config.address)
        driver_type = config_data.get("driver_type", scope_config.driver_type)
        parameters = config_data.get("parameters", scope_config.parameters)
        channels = config_data.get("channels", scope_config.channels)
        yaml_content = config_data.get("yaml_content", scope_config.yaml_content)

        if not name:
            return JsonResponse(
                {"success": False, "error": "Configuration name is required"},
                status=400,
            )

        # Check for duplicate name (excluding current config)
        if ScopeStationConfig.objects.filter(name=name).exclude(id=config_id).exists():
            return JsonResponse(
                {
                    "success": False,
                    "error": f"A Scope configuration named '{name}' already exists",
                },
                status=400,
            )

        # Normalize parameters to ensure qcodes compatibility
        parameters = _normalize_scope_parameters(parameters)

        scope_config.name = name
        scope_config.description = description
        scope_config.address = address
        scope_config.driver_type = driver_type
        scope_config.parameters = parameters
        scope_config.channels = channels
        scope_config.yaml_content = yaml_content
        scope_config.save()

        return JsonResponse(
            {
                "success": True,
                "message": "Scope configuration updated successfully",
                "config": {
                    "id": scope_config.id,
                    "name": scope_config.name,
                    "description": scope_config.description,
                    "is_mock": scope_config.is_mock,
                    "address": scope_config.address,
                    "driver_type": scope_config.driver_type,
                    "parameters": scope_config.parameters,
                    "channels": scope_config.channels,
                },
            }
        )

    except Exception as e:
        import traceback

        traceback.print_exc()
        return JsonResponse({"success": False, "error": str(e)}, status=400)


def delete_scope_config(request, config_id):
    """Delete a Scope configuration."""
    try:
        try:
            config = ScopeStationConfig.objects.get(id=config_id)
        except ScopeStationConfig.DoesNotExist:
            return JsonResponse(
                {"success": False, "error": "Scope configuration not found"}, status=404
            )

        config_name = config.name
        config.delete()

        return JsonResponse(
            {
                "success": True,
                "message": f"Scope configuration '{config_name}' deleted successfully",
            }
        )

    except Exception as e:
        import traceback

        traceback.print_exc()
        return JsonResponse({"success": False, "error": str(e)}, status=400)


@require_http_methods(["GET"])
def download_scope_config(request, config_id):
    """Download Scope configuration as YAML file."""
    try:
        config = ScopeStationConfig.objects.get(id=config_id)
        filename = f"{config.name.replace(' ', '_')}_scope.station.yaml"

        # Use the model's to_station_yaml method to generate YAML
        yaml_content = config.to_station_yaml()

        # Create HTTP response with YAML content
        response = HttpResponse(yaml_content, content_type="application/x-yaml")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'

        return response

    except ScopeStationConfig.DoesNotExist:
        return JsonResponse(
            {"success": False, "error": "Scope configuration not found"}, status=404
        )
    except Exception as e:
        import traceback

        traceback.print_exc()
        return JsonResponse({"success": False, "error": str(e)}, status=400)


# ============================================================================
# LUT CONFIG API
# ============================================================================


@require_http_methods(["GET"])
def get_lut_configs(request):
    """Get list of all saved LUT configurations."""
    try:
        configs = LUTConfig.objects.all()

        configs_data = [
            {
                "id": config.id,
                "name": config.name,
                "description": config.description,
                "input_lut": config.input_lut,
                "output_lut": config.output_lut,
                "num_points": len(config.input_lut) if config.input_lut else 0,
                "created_at": config.created_at.isoformat(),
            }
            for config in configs
        ]

        return JsonResponse({"success": True, "configs": configs_data})

    except Exception as e:
        import traceback

        traceback.print_exc()
        return JsonResponse({"success": False, "error": str(e)}, status=400)


@csrf_exempt
@require_http_methods(["GET", "POST"])
def lut_config_list_create(request):
    """Handle GET (list) and POST (create) for LUT configs."""
    if request.method == "GET":
        return get_lut_configs(request)
    elif request.method == "POST":
        return create_lut_config(request)


def create_lut_config(request):
    """Create a new LUT configuration from CSV file upload or JSON data."""
    try:
        # Check if this is a file upload or JSON data
        if request.FILES.get("file"):
            # File upload
            name = request.POST.get("name", "").strip()
            description = request.POST.get("description", "")
            csv_file = request.FILES["file"]

            if not name:
                return JsonResponse(
                    {"success": False, "error": "Configuration name is required"},
                    status=400,
                )

            # Check for duplicate name
            if LUTConfig.objects.filter(name=name).exists():
                return JsonResponse(
                    {
                        "success": False,
                        "error": f"A LUT configuration named '{name}' already exists",
                    },
                    status=400,
                )

            # Read and decode the CSV file
            try:
                content = csv_file.read().decode("utf-8")
            except UnicodeDecodeError:
                return JsonResponse(
                    {"success": False, "error": "File must be UTF-8 encoded"},
                    status=400,
                )

            # Parse CSV
            reader = csv.DictReader(io.StringIO(content))

            input_lut = []
            output_lut = []

            for row_num, row in enumerate(reader, start=2):
                try:
                    input_val = None
                    output_val = None

                    for key in ["input", "Input", "INPUT", "in", "In", "IN"]:
                        if key in row:
                            input_val = float(row[key])
                            break

                    for key in ["output", "Output", "OUTPUT", "out", "Out", "OUT"]:
                        if key in row:
                            output_val = float(row[key])
                            break

                    if input_val is None or output_val is None:
                        return JsonResponse(
                            {
                                "success": False,
                                "error": f"Row {row_num}: Could not find 'input' and 'output' columns. "
                                f"Available columns: {list(row.keys())}",
                            },
                            status=400,
                        )

                    input_lut.append(input_val)
                    output_lut.append(output_val)

                except ValueError as e:
                    return JsonResponse(
                        {
                            "success": False,
                            "error": f"Row {row_num}: Invalid number format - {str(e)}",
                        },
                        status=400,
                    )

            if len(input_lut) < 2:
                return JsonResponse(
                    {
                        "success": False,
                        "error": "LUT must have at least 2 data points",
                    },
                    status=400,
                )

        else:
            # JSON data
            data = json.loads(request.body)
            name = data.get("name", "").strip()
            description = data.get("description", "")
            input_lut = data.get("input_lut", [])
            output_lut = data.get("output_lut", [])

            if not name:
                return JsonResponse(
                    {"success": False, "error": "Configuration name is required"},
                    status=400,
                )

            # Check for duplicate name
            if LUTConfig.objects.filter(name=name).exists():
                return JsonResponse(
                    {
                        "success": False,
                        "error": f"A LUT configuration named '{name}' already exists",
                    },
                    status=400,
                )

            if len(input_lut) < 2 or len(output_lut) < 2:
                return JsonResponse(
                    {
                        "success": False,
                        "error": "LUT must have at least 2 data points",
                    },
                    status=400,
                )

        lut_config = LUTConfig.objects.create(
            name=name,
            description=description,
            input_lut=input_lut,
            output_lut=output_lut,
        )

        return JsonResponse(
            {
                "success": True,
                "message": f"LUT configuration created successfully with {len(input_lut)} points",
                "config": {
                    "id": lut_config.id,
                    "name": lut_config.name,
                    "description": lut_config.description,
                    "input_lut": lut_config.input_lut,
                    "output_lut": lut_config.output_lut,
                    "num_points": len(input_lut),
                },
            }
        )

    except Exception as e:
        import traceback

        traceback.print_exc()
        return JsonResponse({"success": False, "error": str(e)}, status=400)


@csrf_exempt
@require_http_methods(["GET", "PUT", "DELETE"])
def lut_config_detail(request, config_id):
    """Handle GET, PUT, DELETE for a specific LUT config."""
    if request.method == "GET":
        return get_lut_config_detail(request, config_id)
    elif request.method == "PUT":
        return update_lut_config(request, config_id)
    elif request.method == "DELETE":
        return delete_lut_config(request, config_id)


def get_lut_config_detail(request, config_id):
    """Get details of a specific LUT configuration."""
    try:
        config = LUTConfig.objects.get(id=config_id)

        return JsonResponse(
            {
                "success": True,
                "config": {
                    "id": config.id,
                    "name": config.name,
                    "description": config.description,
                    "input_lut": config.input_lut,
                    "output_lut": config.output_lut,
                    "num_points": len(config.input_lut) if config.input_lut else 0,
                    "created_at": config.created_at.isoformat(),
                },
            }
        )

    except LUTConfig.DoesNotExist:
        return JsonResponse(
            {"success": False, "error": "LUT configuration not found"}, status=404
        )
    except Exception as e:
        import traceback

        traceback.print_exc()
        return JsonResponse({"success": False, "error": str(e)}, status=400)


def update_lut_config(request, config_id):
    """Update an existing LUT configuration."""
    try:
        data = json.loads(request.body)

        try:
            lut_config = LUTConfig.objects.get(id=config_id)
        except LUTConfig.DoesNotExist:
            return JsonResponse(
                {"success": False, "error": "LUT configuration not found"}, status=404
            )

        name = data.get("name", lut_config.name).strip()
        description = data.get("description", lut_config.description)

        if not name:
            return JsonResponse(
                {"success": False, "error": "Configuration name is required"},
                status=400,
            )

        # Check for duplicate name (excluding current config)
        if LUTConfig.objects.filter(name=name).exclude(id=config_id).exists():
            return JsonResponse(
                {
                    "success": False,
                    "error": f"A LUT configuration named '{name}' already exists",
                },
                status=400,
            )

        lut_config.name = name
        lut_config.description = description

        # Update LUT data if provided
        if "input_lut" in data and "output_lut" in data:
            lut_config.input_lut = data["input_lut"]
            lut_config.output_lut = data["output_lut"]

        lut_config.save()

        return JsonResponse(
            {
                "success": True,
                "message": "LUT configuration updated successfully",
                "config": {
                    "id": lut_config.id,
                    "name": lut_config.name,
                    "description": lut_config.description,
                    "input_lut": lut_config.input_lut,
                    "output_lut": lut_config.output_lut,
                    "num_points": (
                        len(lut_config.input_lut) if lut_config.input_lut else 0
                    ),
                },
            }
        )

    except Exception as e:
        import traceback

        traceback.print_exc()
        return JsonResponse({"success": False, "error": str(e)}, status=400)


def delete_lut_config(request, config_id):
    """Delete a LUT configuration."""
    try:
        try:
            config = LUTConfig.objects.get(id=config_id)
        except LUTConfig.DoesNotExist:
            return JsonResponse(
                {"success": False, "error": "LUT configuration not found"}, status=404
            )

        config_name = config.name
        config.delete()

        return JsonResponse(
            {
                "success": True,
                "message": f"LUT configuration '{config_name}' deleted successfully",
            }
        )

    except Exception as e:
        import traceback

        traceback.print_exc()
        return JsonResponse({"success": False, "error": str(e)}, status=400)


# ============================================================================
# COMBINED CONFIGS API
# ============================================================================


@require_http_methods(["GET"])
def get_all_configs(request):
    """Get all configurations grouped by type."""
    try:
        awg_configs = AWGStationConfig.objects.all()
        scope_configs = ScopeStationConfig.objects.all()
        lut_configs = LUTConfig.objects.all()

        return JsonResponse(
            {
                "success": True,
                "awg_configs": [
                    {
                        "id": c.id,
                        "name": c.name,
                        "description": c.description,
                        "is_mock": c.is_mock,
                        "address": c.address,
                        "driver_type": c.driver_type,
                        "parameters": c.parameters,
                        "use_flags": c.use_flags,
                        "created_at": c.created_at.isoformat(),
                    }
                    for c in awg_configs
                ],
                "scope_configs": [
                    {
                        "id": c.id,
                        "name": c.name,
                        "description": c.description,
                        "is_mock": c.is_mock,
                        "address": c.address,
                        "driver_type": c.driver_type,
                        "parameters": c.parameters,
                        "channels": c.channels,
                        "created_at": c.created_at.isoformat(),
                    }
                    for c in scope_configs
                ],
                "lut_configs": [
                    {
                        "id": c.id,
                        "name": c.name,
                        "description": c.description,
                        "num_points": len(c.input_lut) if c.input_lut else 0,
                        "created_at": c.created_at.isoformat(),
                    }
                    for c in lut_configs
                ],
            }
        )

    except Exception as e:
        import traceback

        traceback.print_exc()
        return JsonResponse({"success": False, "error": str(e)}, status=400)


@csrf_exempt
@require_http_methods(["POST"])
def configure_instrument(request):
    """Configure an instrument (AWG or Scope) by connecting and applying settings.

    Uses the same code path as Upload - loads the saved config model and uses
    AWGFactory.create_from_model() or ScopeFactory.create_from_model() to ensure
    all initial_value parameters are applied to the hardware.

    Request body should include:
        - instrument_type: 'awg' or 'scope'
        - config_id: ID of the saved configuration to use
    """
    try:
        data = json.loads(request.body)

        instrument_type = data.get("instrument_type")  # 'awg' or 'scope'
        config_id = data.get("config_id")

        if not instrument_type:
            return JsonResponse(
                {"success": False, "error": "instrument_type is required"}, status=400
            )

        if not config_id:
            return JsonResponse(
                {
                    "success": False,
                    "error": "config_id is required. Please save the configuration first.",
                },
                status=400,
            )

        try:
            if instrument_type == "awg":
                # Load AWG config model from database
                config_model = AWGStationConfig.objects.get(id=config_id)

                # For MOCK instruments, always succeed
                if config_model.is_mock:
                    return JsonResponse(
                        {
                            "success": True,
                            "message": "Mock AWG configuration successful (simulation mode)",
                        }
                    )

                # Create AWG using factory from model - same code path as Upload
                logger.info(f"Configuring AWG from config_id={config_id}")
                awg = AWGFactory.create_from_model(config_model)

                # Read back sample_rate to confirm connection and parameters applied
                try:
                    sample_rate = awg.awg.sample_rate()
                    logger.info(f"AWG configured: sample_rate={sample_rate}")
                except Exception as read_error:
                    logger.warning(f"Could not read sample_rate: {read_error}")
                    sample_rate = None

                # Disconnect after configuration
                awg.disconnect()

                message = f"AWG configured successfully at {config_model.address}"
                if sample_rate is not None:
                    message += f" (sample_rate: {sample_rate/1e9:.2f} GSa/s)"

                return JsonResponse({"success": True, "message": message})

            elif instrument_type == "scope":
                # Load Scope config model from database
                config_model = ScopeStationConfig.objects.get(id=config_id)

                # For MOCK instruments, always succeed
                if config_model.is_mock:
                    return JsonResponse(
                        {
                            "success": True,
                            "message": "Mock Scope configuration successful (simulation mode)",
                        }
                    )

                # Create Scope using factory from model - same code path as Upload
                logger.info(f"Configuring Scope from config_id={config_id}")
                scope = ScopeFactory.create_from_model(config_model)

                # Read back a parameter to confirm connection and parameters applied
                try:
                    time_unit, _ = scope.timebase()
                    logger.info(f"Scope configured: time_unit={time_unit}")
                    readback_info = f"time_unit: {time_unit}"
                except Exception as read_error:
                    logger.warning(f"Could not read timebase: {read_error}")
                    readback_info = None

                # Disconnect after configuration
                scope.disconnect()

                message = f"Scope configured successfully at {config_model.address}"
                if readback_info:
                    message += f" ({readback_info})"

                return JsonResponse({"success": True, "message": message})

            else:
                return JsonResponse(
                    {
                        "success": False,
                        "error": f"Unknown instrument type: {instrument_type}",
                    },
                    status=400,
                )

        except AWGStationConfig.DoesNotExist:
            return JsonResponse(
                {"success": False, "error": "AWG configuration not found"}, status=404
            )
        except ScopeStationConfig.DoesNotExist:
            return JsonResponse(
                {"success": False, "error": "Scope configuration not found"}, status=404
            )
        except Exception as conn_error:
            logger.error(f"Configuration failed: {conn_error}")
            return JsonResponse(
                {"success": False, "error": f"Configuration failed: {str(conn_error)}"}
            )

    except Exception as e:
        import traceback

        traceback.print_exc()
        return JsonResponse({"success": False, "error": str(e)}, status=400)

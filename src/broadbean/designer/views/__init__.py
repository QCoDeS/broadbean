"""Views package for the waveform designer app.

This module re-exports all view functions from the sub-modules for backward
compatibility with urls.py which imports views as `from . import views`.
"""

# Designer views (designer.html)
from .designer_views import (
    delete_waveform_element,
    designer_view,
    export_waveform,
    get_segment_types,
    get_waveform_element,
    get_waveform_elements,
    preview_waveform,
    save_waveform_element,
    update_waveform_element,
)

# Instrument configuration views (instruments.html)
from .instruments_views import (
    awg_config_detail,
    awg_config_list_create,
    configure_instrument,
    download_awg_config,
    download_scope_config,
    # Combined
    get_all_configs,
    # AWG config
    get_awg_configs,
    get_instrument_types,
    # LUT config
    get_lut_configs,
    # Scope config
    get_scope_configs,
    instruments_view,
    lut_config_detail,
    lut_config_list_create,
    scope_config_detail,
    scope_config_list_create,
)

# Parametric generator views (parametric_generator.html)
from .parametric_views import (
    generate_parametric_sequence,
    parametric_generator_view,
)

# Sequencer views (sequencer.html)
from .sequencer_views import (
    delete_sequence,
    download_sequence_data,
    get_sequence_channels,
    get_sequences,
    preview_saved_sequence,
    preview_sequence,
    save_sequence,
    sequence_detail_update,
    sequencer_view,
    update_sequence,
)

# Upload views (upload.html)
from .upload_views import (
    disconnect_instruments,
    jump_to_and_capture,
    trigger_and_capture,
    upload_sequence,
    upload_view,
)

__all__ = [
    # Designer
    "designer_view",
    "get_segment_types",
    "export_waveform",
    "preview_waveform",
    "save_waveform_element",
    "update_waveform_element",
    "delete_waveform_element",
    "get_waveform_elements",
    "get_waveform_element",
    # Instruments
    "instruments_view",
    "get_instrument_types",
    "get_awg_configs",
    "awg_config_list_create",
    "awg_config_detail",
    "download_awg_config",
    "get_scope_configs",
    "scope_config_list_create",
    "scope_config_detail",
    "download_scope_config",
    "get_lut_configs",
    "lut_config_list_create",
    "lut_config_detail",
    "get_all_configs",
    "configure_instrument",
    # Sequencer
    "sequencer_view",
    "preview_sequence",
    "save_sequence",
    "get_sequences",
    "sequence_detail_update",
    "update_sequence",
    "download_sequence_data",
    "delete_sequence",
    "get_sequence_channels",
    "preview_saved_sequence",
    # Upload
    "upload_view",
    "upload_sequence",
    "trigger_and_capture",
    "jump_to_and_capture",
    "disconnect_instruments",
    # Parametric
    "parametric_generator_view",
    "generate_parametric_sequence",
]

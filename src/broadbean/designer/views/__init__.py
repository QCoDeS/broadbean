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
    "awg_config_detail",
    "awg_config_list_create",
    "configure_instrument",
    "delete_sequence",
    "delete_waveform_element",
    "designer_view",
    "disconnect_instruments",
    "download_awg_config",
    "download_scope_config",
    "download_sequence_data",
    "export_waveform",
    "generate_parametric_sequence",
    "get_all_configs",
    "get_awg_configs",
    "get_instrument_types",
    "get_lut_configs",
    "get_scope_configs",
    "get_segment_types",
    "get_sequence_channels",
    "get_sequences",
    "get_waveform_element",
    "get_waveform_elements",
    "instruments_view",
    "jump_to_and_capture",
    "lut_config_detail",
    "lut_config_list_create",
    "parametric_generator_view",
    "preview_saved_sequence",
    "preview_sequence",
    "preview_waveform",
    "save_sequence",
    "save_waveform_element",
    "scope_config_detail",
    "scope_config_list_create",
    "sequence_detail_update",
    "sequencer_view",
    "trigger_and_capture",
    "update_sequence",
    "update_waveform_element",
    "upload_sequence",
    "upload_view",
]

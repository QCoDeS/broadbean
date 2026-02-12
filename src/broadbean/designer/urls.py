"""URL configuration for waveform_designer app."""

from django.urls import path
from . import views

app_name = "waveform_designer"

urlpatterns = [
    # Main views
    path("", views.designer_view, name="designer"),
    path("sequencer/", views.sequencer_view, name="sequencer"),
    path("upload/", views.upload_view, name="upload"),
    path("parametric/", views.parametric_generator_view, name="parametric_generator"),
    path("instruments/", views.instruments_view, name="instruments"),
    # API - Instrument Types
    path("api/instrument-types/", views.get_instrument_types, name="instrument_types"),
    # API - Segments
    path("api/segments/", views.get_segment_types, name="segment_types"),
    # API - Waveform Elements
    path("api/waveform/preview/", views.preview_waveform, name="preview_waveform"),
    path("api/waveform/export/", views.export_waveform, name="export_waveform"),
    path("api/waveform/save/", views.save_waveform_element, name="save_waveform"),
    path(
        "api/waveform/update/<int:element_id>/",
        views.update_waveform_element,
        name="update_waveform",
    ),
    path(
        "api/waveform/delete/<int:element_id>/",
        views.delete_waveform_element,
        name="delete_waveform",
    ),
    path("api/elements/", views.get_waveform_elements, name="get_elements"),
    path(
        "api/elements/<int:element_id>/", views.get_waveform_element, name="get_element"
    ),
    # API - Sequences
    path("api/sequence/preview/", views.preview_sequence, name="preview_sequence"),
    path("api/sequence/save/", views.save_sequence, name="save_sequence"),
    path("api/sequences/", views.get_sequences, name="get_sequences"),
    path(
        "api/sequences/<int:sequence_id>/",
        views.sequence_detail_update,
        name="sequence_detail_update",
    ),
    path(
        "api/sequences/delete/<int:sequence_id>/",
        views.delete_sequence,
        name="delete_sequence",
    ),
    path(
        "api/sequences/<int:sequence_id>/preview/",
        views.preview_saved_sequence,
        name="preview_saved_sequence",
    ),
    path(
        "api/sequences/<int:sequence_id>/channels/",
        views.get_sequence_channels,
        name="get_sequence_channels",
    ),
    path(
        "api/sequences/<int:sequence_id>/download/",
        views.download_sequence_data,
        name="download_sequence_data",
    ),
    # API - Upload & Capture (using mock instruments)
    path("api/upload-sequence/", views.upload_sequence, name="upload_sequence"),
    path(
        "api/trigger-and-capture/",
        views.trigger_and_capture,
        name="trigger_and_capture",
    ),
    path(
        "api/jump-to-and-capture/",
        views.jump_to_and_capture,
        name="jump_to_and_capture",
    ),
    path(
        "api/disconnect-instruments/",
        views.disconnect_instruments,
        name="disconnect_instruments",
    ),
    # API - Parametric Generator
    path(
        "api/parametric/generate/",
        views.generate_parametric_sequence,
        name="generate_parametric_sequence",
    ),
    # API - AWG Configurations
    path(
        "api/awg-configs/",
        views.awg_config_list_create,
        name="awg_configs",
    ),
    path(
        "api/awg-configs/<int:config_id>/",
        views.awg_config_detail,
        name="awg_config_detail",
    ),
    path(
        "api/awg-configs/<int:config_id>/download/",
        views.download_awg_config,
        name="download_awg_config",
    ),
    # API - Scope Configurations
    path(
        "api/scope-configs/",
        views.scope_config_list_create,
        name="scope_configs",
    ),
    path(
        "api/scope-configs/<int:config_id>/",
        views.scope_config_detail,
        name="scope_config_detail",
    ),
    path(
        "api/scope-configs/<int:config_id>/download/",
        views.download_scope_config,
        name="download_scope_config",
    ),
    # API - LUT Configurations
    path(
        "api/lut-configs/",
        views.lut_config_list_create,
        name="lut_configs",
    ),
    path(
        "api/lut-configs/<int:config_id>/",
        views.lut_config_detail,
        name="lut_config_detail",
    ),
    # API - All Configs (combined endpoint)
    path(
        "api/all-configs/",
        views.get_all_configs,
        name="all_configs",
    ),
    # API - Configure Instrument (connect and apply settings)
    path(
        "api/instrument-configs/test/",
        views.configure_instrument,
        name="configure_instrument",
    ),
]

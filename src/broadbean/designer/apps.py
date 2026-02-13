"""App configuration for waveform_designer."""

from django.apps import AppConfig


class WaveformDesignerConfig(AppConfig):
    """Configuration for the waveform designer app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "broadbean.designer"
    verbose_name = "Waveform Designer"

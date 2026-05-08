"""Admin configuration for waveform designer models."""

from django.contrib import admin

from .models import SequenceElement, WaveformElement, WaveformSequence


@admin.register(WaveformElement)
class WaveformElementAdmin(admin.ModelAdmin):
    """Admin interface for WaveformElement."""

    list_display = (
        "name",
        "duration",
        "num_channels",
        "sample_rate",
        "created_at",
    )
    list_filter = ("created_at", "num_channels")
    search_fields = ("name", "description")
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        ("Basic Information", {"fields": ("name", "description")}),
        ("Waveform Data", {"fields": ("element_data",)}),
        ("Metadata", {"fields": ("sample_rate", "duration", "num_channels")}),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    # Enable delete functionality
    actions = ["delete_selected"]

    def has_delete_permission(self, request, obj=None):
        """Allow deletion of WaveformElement objects."""
        return True


class SequenceElementInline(admin.TabularInline):
    """Inline admin for SequenceElement."""

    model = SequenceElement
    extra = 0
    fields = (
        "position",
        "waveform_element",
        "trigger_input",
        "repetitions",
        "goto_position",
    )
    ordering = ("position",)

    # Enable delete functionality
    actions = ["delete_selected"]

    def has_delete_permission(self, request, obj=None):
        """Allow deletion of SequenceElement objects."""
        return True


@admin.register(WaveformSequence)
class WaveformSequenceAdmin(admin.ModelAdmin):
    """Admin interface for WaveformSequence."""

    list_display = (
        "name",
        "num_positions",
        "total_duration",
        "created_at",
    )
    list_filter = ("created_at",)
    search_fields = ("name", "description")
    readonly_fields = ("created_at", "updated_at")
    inlines = [SequenceElementInline]
    fieldsets = (
        ("Basic Information", {"fields": ("name", "description")}),
        ("Sequence Data", {"fields": ("sequence_data",)}),
        ("Metadata", {"fields": ("num_positions", "total_duration")}),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    # Enable delete functionality
    actions = ["delete_selected"]

    def has_delete_permission(self, request, obj=None):
        """Allow deletion of WaveformSequence objects."""
        return True


@admin.register(SequenceElement)
class SequenceElementAdmin(admin.ModelAdmin):
    """Admin interface for SequenceElement."""

    list_display = (
        "sequence",
        "position",
        "waveform_element",
        "trigger_input",
        "repetitions",
        "goto_position",
    )
    list_filter = ("sequence", "trigger_input")
    search_fields = ("sequence__name", "waveform_element__name")
    ordering = ("sequence", "position")

    # Enable delete functionality
    actions = ["delete_selected"]

    def has_delete_permission(self, request, obj=None):
        """Allow deletion of SequenceElement objects."""
        return True

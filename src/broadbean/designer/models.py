"""Models for the waveform designer app."""

from django.core.validators import MinValueValidator
from django.db import models

from broadbean.instruments.registry import AWGDriver, InstrumentRegistry, ScopeDriver

# Constants for backward compatibility and model field defaults
AWG_DRIVER_MOCK = AWGDriver.MOCK.value
AWG_DRIVER_CHOICES = InstrumentRegistry.get_awg_choices()
SCOPE_DRIVER_MOCK = ScopeDriver.MOCK.value
SCOPE_DRIVER_CHOICES = InstrumentRegistry.get_scope_choices()


class WaveformElement(models.Model):
    """
    A saved waveform element created in the designer UI.
    Stores the complete broadbean Element configuration as JSON.
    """

    name = models.CharField(max_length=200, help_text="Name of the waveform element")
    description = models.TextField(blank=True, help_text="Optional description")

    # Store the complete element data
    element_data = models.JSONField(help_text="Complete broadbean Element JSON")

    # Metadata
    sample_rate = models.FloatField(help_text="Sample rate in Hz")
    duration = models.FloatField(help_text="Total duration in seconds")
    num_channels = models.IntegerField(default=1, help_text="Number of channels")
    is_auto_generated = models.BooleanField(
        default=False,
        help_text="True if this element was automatically generated (e.g., from parametric sweep)",
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Waveform Element"
        verbose_name_plural = "Waveform Elements"

    def __str__(self):
        return f"{self.name} ({self.duration * 1e6:.2f}μs)"


class WaveformSequence(models.Model):
    """
    A waveform sequence composed of multiple WaveformElements.
    Defines the order and sequencing parameters for each element.
    """

    name = models.CharField(max_length=200, help_text="Name of the sequence")
    description = models.TextField(blank=True, help_text="Optional description")

    # Store complete sequence configuration
    sequence_data = models.JSONField(help_text="Complete sequence configuration")

    # Metadata
    total_duration = models.FloatField(
        help_text="Total sequence duration in seconds", null=True, blank=True
    )
    num_positions = models.IntegerField(
        default=0, help_text="Number of positions in sequence"
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Waveform Sequence"
        verbose_name_plural = "Waveform Sequences"

    def __str__(self):
        return f"{self.name} ({self.num_positions} positions)"


class SequenceElement(models.Model):
    """
    Intermediary model linking WaveformElements to WaveformSequences.
    Defines the sequencing parameters for each element in a sequence.
    """

    sequence = models.ForeignKey(
        WaveformSequence, on_delete=models.CASCADE, related_name="elements"
    )
    waveform_element = models.ForeignKey(
        WaveformElement, on_delete=models.CASCADE, related_name="sequence_uses"
    )

    # Position in the sequence (1-indexed to match broadbean)
    position = models.IntegerField(
        validators=[MinValueValidator(1)], help_text="Position in sequence (1-indexed)"
    )

    # Sequencing parameters
    trigger_input = models.IntegerField(
        default=0,
        choices=[
            (0, "Trigger 0"),
            (1, "Trigger 1"),
            (2, "Trigger 2"),
            (3, "Trigger 3"),
        ],
        help_text="Trigger input to wait for (0-3)",
    )
    repetitions = models.IntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        help_text="Number of times to repeat this element",
    )
    goto_position = models.IntegerField(
        null=True,
        blank=True,
        help_text="Next position to jump to (null for default behavior)",
    )
    flags = models.JSONField(
        null=True,
        blank=True,
        help_text="Channel flags configuration: {channel_1: [A, B, C, D], ...}",
    )

    class Meta:
        ordering = ["sequence", "position"]
        unique_together = ["sequence", "position"]
        verbose_name = "Sequence Element"
        verbose_name_plural = "Sequence Elements"

    def __str__(self):
        return (
            f"{self.sequence.name} - Pos {self.position}: {self.waveform_element.name}"
        )


# ---------------------------------------------------------------------------
# AWG station configuration
# ---------------------------------------------------------------------------
class AWGStationConfig(models.Model):
    """
    Stores AWG instrument configuration in qcodes Station YAML format.
    These configurations can be selected on the Upload & Capture page.
    Supports both UI-configured parameters and external YAML file imports.
    """

    name = models.CharField(max_length=200, unique=True, help_text="Configuration name")
    description = models.TextField(blank=True, help_text="Optional description")

    # VISA address for the instrument
    address = models.CharField(
        max_length=200,
        default="TCPIP0::192.168.0.2::inst0::INSTR",
        help_text="VISA address for the AWG",
    )

    # Driver type - primary discriminator for instrument type
    # "mock" = simulation mode, qcodes driver path = real hardware
    driver_type = models.CharField(
        max_length=200,
        choices=AWG_DRIVER_CHOICES,
        default=AWG_DRIVER_MOCK,
        help_text="Instrument driver type: 'mock' for simulation or qcodes driver path for real hardware",
    )

    # Parameters stored as JSON (matches qcodes station YAML parameters section)
    parameters = models.JSONField(
        default=dict,
        help_text="AWG parameters in qcodes Station format",
    )

    # Whether to use flags in sequence output
    use_flags = models.BooleanField(
        default=False,
        help_text="Whether to use flags when outputting sequence files",
    )

    # VISA timeout in seconds
    visa_timeout = models.IntegerField(
        default=60,
        help_text="VISA connection timeout in seconds",
    )

    # Optional: store raw YAML content for imported configurations
    yaml_content = models.TextField(
        blank=True,
        help_text="Raw YAML content (for imported configurations)",
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "AWG Station Configuration"
        verbose_name_plural = "AWG Station Configurations"

    @property
    def is_mock(self) -> bool:
        """Return True if this is a mock/simulation configuration."""
        return self.driver_type == AWG_DRIVER_MOCK

    def __str__(self):
        mode = "MOCK" if self.is_mock else "HARDWARE"
        return f"{self.name} ({mode})"

    def to_station_yaml(self) -> str:
        """Generate qcodes Station YAML configuration string."""
        import yaml

        from broadbean.instruments.registry import AWGDriver

        if self.is_mock:
            # Mock mode doesn't need a real YAML config
            return "# Mock AWG - no hardware configuration\n"

        # Map driver keys to qcodes driver paths
        qcodes_driver_map = {
            AWGDriver.TEKTRONIX_70002A.value: "qcodes.instrument_drivers.tektronix.TektronixAWG70002A",
            AWGDriver.TEKTRONIX_70001A.value: "qcodes.instrument_drivers.tektronix.TektronixAWG70001A",
        }
        qcodes_driver = qcodes_driver_map.get(self.driver_type, self.driver_type)

        config = {
            "instruments": {
                "awg": {
                    "type": qcodes_driver,
                    "address": self.address,
                    "parameters": self.parameters,
                }
            }
        }
        return yaml.dump(config, default_flow_style=False, sort_keys=False)

    def to_config_dict(self) -> dict:
        """Return configuration as a dictionary for StationAWG."""
        return {
            "address": self.address,
            "driver_type": self.driver_type,
            "parameters": self.parameters,
            "visa_timeout": self.visa_timeout,
        }

    @classmethod
    def get_default_parameters(cls):
        """Return default AWG parameters in qcodes Station format."""
        return {
            "mode": {"initial_value": "AWG"},
            "sample_rate": {
                "initial_value": 25e9,
                "label": "Sample Rate",
                "unit": "Sa/s",
            },
            "clock_source": {"initial_value": "Internal"},
            "all_output_off": {"initial_value": True},
            "ch1.resolution": {
                "initial_value": 8,
                "label": "Channel 1 Resolution",
                "unit": "bits",
            },
            "ch1.awg_amplitude": {
                "initial_value": 0.5,
                "label": "Channel 1 Amplitude",
                "unit": "Vpp",
            },
            "ch1.hold": {"initial_value": "FIRST"},
            "ch2.resolution": {
                "initial_value": 10,
                "label": "Channel 2 Resolution",
                "unit": "bits",
            },
            "ch2.awg_amplitude": {
                "initial_value": 0.5,
                "label": "Channel 2 Amplitude",
                "unit": "Vpp",
            },
            "ch2.hold": {"initial_value": "FIRST"},
        }


# ---------------------------------------------------------------------------
# LUT calibration configuration
# ---------------------------------------------------------------------------
class LUTConfig(models.Model):
    """
    Stores LUT (Lookup Table) calibration configuration for AWG amplitude correction.
    LUTs can be assigned per-channel on the Upload & Capture page.
    """

    name = models.CharField(max_length=200, unique=True, help_text="Configuration name")
    description = models.TextField(blank=True, help_text="Optional description")

    # LUT data stored as separate lists
    input_lut = models.JSONField(
        help_text="List of input values for the LUT",
    )
    output_lut = models.JSONField(
        help_text="List of output values for the LUT",
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "LUT Configuration"
        verbose_name_plural = "LUT Configurations"

    def __str__(self):
        num_points = len(self.input_lut) if self.input_lut else 0
        return f"{self.name} ({num_points} points)"


# ---------------------------------------------------------------------------
# Scope station configuration
# ---------------------------------------------------------------------------
class ScopeStationConfig(models.Model):
    """
    Stores Scope instrument configuration in qcodes Station YAML format.
    These configurations can be selected on the Upload & Capture page.
    Supports both UI-configured parameters and external YAML file imports.
    """

    name = models.CharField(max_length=200, unique=True, help_text="Configuration name")
    description = models.TextField(blank=True, help_text="Optional description")

    # VISA address for the instrument
    address = models.CharField(
        max_length=200,
        default="TCPIP0::192.168.0.3::inst0::INSTR",
        help_text="VISA address for the Scope",
    )

    # Driver type - primary discriminator for instrument type
    # "mock" = simulation mode, qcodes driver path = real hardware
    driver_type = models.CharField(
        max_length=200,
        choices=SCOPE_DRIVER_CHOICES,
        default=SCOPE_DRIVER_MOCK,
        help_text="Instrument driver type: 'mock' for simulation or qcodes driver path for real hardware",
    )

    # Parameters stored as JSON (matches qcodes station YAML parameters section)
    parameters = models.JSONField(
        default=dict,
        help_text="Scope parameters in qcodes Station format",
    )

    # Channel configurations (list of enabled channels with their settings)
    channels = models.JSONField(
        default=list,
        help_text="List of channel configurations: [{number, coupling, scale, offset, position, enabled}, ...]",
    )

    # VISA timeout in seconds
    visa_timeout = models.IntegerField(
        default=60,
        help_text="VISA connection timeout in seconds",
    )

    # Optional: store raw YAML content for imported configurations
    yaml_content = models.TextField(
        blank=True,
        help_text="Raw YAML content (for imported configurations)",
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Scope Station Configuration"
        verbose_name_plural = "Scope Station Configurations"

    @property
    def is_mock(self) -> bool:
        """Return True if this is a mock/simulation configuration."""
        return self.driver_type == SCOPE_DRIVER_MOCK

    def __str__(self):
        mode = "MOCK" if self.is_mock else "HARDWARE"
        return f"{self.name} ({mode})"

    def _build_all_parameters(self) -> dict:
        """Build parameters dict including channel configurations.

        Merges base parameters with per-channel settings for all enabled
        channels, producing the combined dict used by both
        ``to_station_yaml`` and ``to_config_dict``.

        Channel data format: {"source": "CH1", "enabled": "ON", ...}
        """
        all_parameters = dict(self.parameters)

        for ch_config in self.channels:
            source = ch_config.get("source", "CH1")
            if source.upper().startswith("CH"):
                try:
                    ch_num = int(source[2:])
                except ValueError:
                    ch_num = 1
            else:
                ch_num = 1

            ch_prefix = f"channel{ch_num}"

            enabled = ch_config.get("enabled", "OFF")
            if isinstance(enabled, str):
                enabled = enabled.upper() == "ON"

            if enabled:
                if "coupling" in ch_config:
                    all_parameters[f"{ch_prefix}.coupling"] = {
                        "initial_value": ch_config["coupling"]
                    }
                if "scale" in ch_config:
                    all_parameters[f"{ch_prefix}.scale"] = {
                        "initial_value": ch_config["scale"],
                        "label": f"Channel {ch_num} Scale",
                        "unit": "V/div",
                    }
                if "offset" in ch_config:
                    all_parameters[f"{ch_prefix}.offset"] = {
                        "initial_value": ch_config["offset"],
                        "label": f"Channel {ch_num} Offset",
                        "unit": "V",
                    }
                if "position" in ch_config:
                    all_parameters[f"{ch_prefix}.position"] = {
                        "initial_value": ch_config["position"],
                        "label": f"Channel {ch_num} Position",
                        "unit": "div",
                    }

        return all_parameters

    def to_station_yaml(self) -> str:
        """Generate qcodes Station YAML configuration string."""
        import yaml

        from broadbean.instruments.registry import ScopeDriver

        if self.is_mock:
            # Mock mode doesn't need a real YAML config
            return "# Mock Scope - no hardware configuration\n"

        # Map driver keys to qcodes driver paths
        qcodes_driver_map = {
            ScopeDriver.TEKTRONIX_DPO70000.value: "qcodes.instrument_drivers.tektronix.TektronixDPO70000",
            ScopeDriver.TEKTRONIX_DPO7200.value: "qcodes.instrument_drivers.tektronix.DPO7200xx",
        }
        qcodes_driver = qcodes_driver_map.get(self.driver_type, self.driver_type)

        config = {
            "instruments": {
                "scope": {
                    "type": qcodes_driver,
                    "address": self.address,
                    "parameters": self._build_all_parameters(),
                }
            }
        }
        return yaml.dump(config, default_flow_style=False, sort_keys=False)

    def to_config_dict(self) -> dict:
        """Return configuration as a dictionary for StationScope."""
        return {
            "address": self.address,
            "driver_type": self.driver_type,
            "parameters": self._build_all_parameters(),
            "visa_timeout": self.visa_timeout,
        }

    def get_enabled_channels(self) -> list:
        """Return list of enabled channel numbers.

        Channel data format: {"source": "CH1", "enabled": "ON", ...}
        """
        result = []
        for ch in self.channels:
            enabled = ch.get("enabled", "OFF")
            if isinstance(enabled, str):
                enabled = enabled.upper() == "ON"

            if enabled:
                source = ch.get("source", "CH1")
                if source.upper().startswith("CH"):
                    try:
                        ch_num = int(source[2:])
                    except ValueError:
                        ch_num = 1
                else:
                    ch_num = 1
                result.append(ch_num)
        return result

    @classmethod
    def get_default_parameters(cls):
        """Return default Scope parameters in qcodes Station format."""
        return {
            "acquisition.state": {"initial_value": "STOP"},
            "acquisition.mode": {"initial_value": "sample"},
            "trigger.type": {"initial_value": "edge"},
            "trigger.source": {"initial_value": "AUX"},
            "trigger.level": {
                "initial_value": 0.5,
                "label": "Trigger Level",
                "unit": "V",
            },
            "horizontal.mode": {"initial_value": "auto"},
            "horizontal.position": {
                "initial_value": 0,
                "label": "Horizontal Position",
                "unit": "s",
            },
            "horizontal.scale": {
                "initial_value": 100e-9,
                "label": "Horizontal Scale",
                "unit": "s/div",
            },
            "horizontal.sample_rate": {
                "initial_value": 2.5e9,
                "label": "Sample Rate",
                "unit": "Sa/s",
            },
        }

    @classmethod
    def get_default_channels(cls):
        """Return default channel configurations."""
        return [
            {
                "number": 1,
                "coupling": "DC",
                "scale": 0.05,
                "offset": 0,
                "position": 0,
                "enabled": True,
            },
            {
                "number": 3,
                "coupling": "DC",
                "scale": 0.05,
                "offset": 0,
                "position": 0,
                "enabled": True,
            },
        ]

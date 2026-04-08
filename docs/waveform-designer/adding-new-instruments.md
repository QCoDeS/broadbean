# Adding New AWG and Scope Instruments

This guide explains how to add support for new AWG (Arbitrary Waveform Generator) and Scope (Oscilloscope) instruments to the broadbean Waveform Designer system.

## Architecture Overview

The instrument system uses a **registry-based factory pattern**:

```
src/broadbean/
├── instruments/
│   ├── base/
│   │   ├── awg.py              # ArbitraryWaveformGenerator ABC
│   │   └── scope.py            # Scope ABC
│   │
│   ├── __init__.py             # Package exports
│   ├── registry.py             # Central registry + driver enums
│   ├── mock.py                 # MockAWG + MockScope for simulation
│   ├── qcodes_base.py          # QCodesStationMixin for qcodes instruments
│   ├── awg/
│   │   ├── __init__.py
│   │   └── tektronix.py        # Tektronix AWG implementations
│   └── scope/
│       ├── __init__.py
│       └── tektronix.py        # Tektronix Scope implementations
│
└── interface/
    ├── awg.py                  # AWGFactory
    └── scope.py                # ScopeFactory
```

## Quick Start: Adding a New AWG

### Step 1: Add Driver Key to Registry

Edit `src/broadbean/instruments/registry.py`:

```python
class AWGDriver(Enum):
    """Supported AWG driver types."""
    MOCK = "mock"
    TEKTRONIX_70002A = "tektronix_awg70002a"
    TEKTRONIX_70001A = "tektronix_awg70001a"
    # Add your new driver here:
    KEYSIGHT_M8195A = "keysight_m8195a"
```

### Step 2: Create Implementation File

Create a new file, e.g., `src/broadbean/instruments/awg/keysight.py`:

```python
"""Keysight AWG implementations."""

import logging
from broadbean.sequence import Sequence

from broadbean.instruments.base.awg import ArbitraryWaveformGenerator
from broadbean.instruments.qcodes_base import QCodesStationMixin
from broadbean.instruments.registry import InstrumentRegistry

logger = logging.getLogger(__name__)


@InstrumentRegistry.register_awg("keysight_m8195a")
class KeysightM8195A(QCodesStationMixin, ArbitraryWaveformGenerator):
    """Keysight M8195A AWG implementation.

    High-performance 65 GSa/s arbitrary waveform generator.

    Args:
        config: Configuration dictionary with:
            - address: VISA address for the AWG
            - parameters: Dict of parameter configurations
        flags: Whether to use flags when outputting sequence files.
        **kwargs: Additional arguments (ignored).
    """

    INSTRUMENT_NAME = "awg"
    QCODES_DRIVER = "qcodes.instrument_drivers.keysight.KeysightM8195A"

    def __init__(self, config: dict, flags: bool = False, **kwargs):
        self.flags = flags
        self._init_station(config)
        self.awg = self.station.load_awg()

        # Log basic info
        try:
            sample_rate = self.awg.sample_rate()
            logger.info("AWG loaded - Sample rate: %s Sa/s", sample_rate)
        except Exception as e:
            logger.warning("Could not read sample rate: %s", e)

    def upload(self, sequence: Sequence):
        """Upload a sequence to the AWG.

        Note: Keysight AWGs may use different upload methods than Tektronix.
        Implement the appropriate logic here.
        """
        sequence_name = getattr(sequence, "name", "sequence")
        logger.info("Uploading sequence '%s' to Keysight AWG", sequence_name)

        # Example: Keysight might use WFM files instead of SEQX
        # wfm_data = sequence.outputForWFMFile()
        # self.awg.upload_wfm(wfm_data, sequence_name=sequence_name)

        # Or if it supports SEQX format:
        if self.flags:
            seqx_input = sequence.outputForSEQXFileWithFlags()
        else:
            seqx_input = sequence.outputForSEQXFile()

        self.awg.upload_seqx(seqx_input, sequence_name=sequence_name)
        logger.info("Sequence '%s' uploaded", sequence_name)

    def jump_to(self, index: int):
        """Jump to a specific sequence position."""
        logger.debug("Jumping to sequence position %d", index)
        self.awg.sequence_jump(index)  # Method name may differ

    def trigger(self):
        """Trigger the AWG."""
        logger.debug("Triggering AWG")
        self.awg.trigger()  # Method name may differ

    def trigger_segment(self, segment: int):
        """Jump to a segment and trigger."""
        self.jump_to(segment)
        self.trigger()

    def disconnect(self):
        """Disconnect from the AWG."""
        self._disconnect_station()
```

### Step 3: Register the Module

Edit `src/broadbean/instruments/awg/__init__.py`:

```python
"""AWG instrument implementations."""

from broadbean.instruments.awg.tektronix import (
    TektronixAWG70001A,
    TektronixAWG70002A,
)
from broadbean.instruments.awg.keysight import (  # Add this
    KeysightM8195A,
)

__all__ = [
    "TektronixAWG70001A",
    "TektronixAWG70002A",
    "KeysightM8195A",  # Add this
]
```

### Step 4: Update Main Package Init (Optional)

Edit `src/broadbean/instruments/__init__.py` to export the new class:

```python
from broadbean.instruments.awg import TektronixAWG70001A, TektronixAWG70002A, KeysightM8195A
```

### Step 5: Update Database (for existing installations)

If updating an existing installation, create a migration if needed to add the new driver type as an option.

---

## Quick Start: Adding a New Scope

### Step 1: Add Driver Key to Registry

Edit `src/broadbean/instruments/registry.py`:

```python
class ScopeDriver(Enum):
    """Supported Scope driver types."""
    MOCK = "mock"
    TEKTRONIX_DPO70000 = "tektronix_dpo70000"
    TEKTRONIX_DPO7200 = "tektronix_dpo7200"
    # Add your new driver here:
    LECROY_HDO9000 = "lecroy_hdo9000"
```

### Step 2: Create Implementation File

Create `src/broadbean/instruments/scope/lecroy.py`:

```python
"""LeCroy scope implementations."""

import logging
from typing import Tuple

from broadbean.instruments.base.scope import Scope
from broadbean.instruments.qcodes_base import QCodesStationMixin
from broadbean.instruments.registry import InstrumentRegistry

logger = logging.getLogger(__name__)


@InstrumentRegistry.register_scope("lecroy_hdo9000")
class LecroyHDO9000(QCodesStationMixin, Scope):
    """LeCroy HDO9000 series oscilloscope implementation.

    High Definition Oscilloscope with 12-bit resolution.

    Args:
        config: Configuration dictionary with:
            - address: VISA address for the scope
            - parameters: Dict of parameter configurations
        **kwargs: Additional arguments (ignored).
    """

    INSTRUMENT_NAME = "scope"
    QCODES_DRIVER = "qcodes.instrument_drivers.lecroy.LecroyHDO9000"

    def __init__(self, config: dict, **kwargs):
        self._init_station(config)
        self.scope = self.station.load_scope(update_snapshot=False)
        logger.info("LeCroy scope loaded successfully")

    def single(self):
        """Set scope into single acquisition mode."""
        logger.debug("Setting scope to single acquisition mode")
        # LeCroy method - adjust as needed
        self.scope.trigger_mode("single")
        self.scope.arm()
        logger.debug("Scope ready for triggered acquisition")

    def download(self) -> Tuple:
        """Download acquired waveforms from enabled channels.

        Returns:
            Tuple of numpy arrays, one per enabled channel.
        """
        logger.debug("Downloading waveforms from scope")
        waveforms = self.scope.get_waveforms()  # Method may differ
        logger.info("Downloaded %d waveforms", len(waveforms))
        return waveforms

    def timebase(self) -> Tuple[str, any]:
        """Get the timebase information from the scope.

        Returns:
            Tuple of (time_unit: str, time_axis: np.ndarray)
        """
        logger.debug("Getting timebase from scope")
        # LeCroy specific implementation
        time_div = self.scope.time_div()
        record_length = self.scope.record_length()
        import numpy as np
        time_axis = np.linspace(-5 * time_div, 5 * time_div, record_length)
        return "s", time_axis

    def disconnect(self):
        """Disconnect from the scope."""
        self._disconnect_station()
```

### Step 3: Register the Module

Edit `src/broadbean/instruments/scope/__init__.py`:

```python
"""Scope instrument implementations."""

from broadbean.instruments.scope.tektronix import (
    TektronixDPO70000,
    TektronixDPO7200,
)
from broadbean.instruments.scope.lecroy import (  # Add this
    LecroyHDO9000,
)

__all__ = [
    "TektronixDPO70000",
    "TektronixDPO7200",
    "LecroyHDO9000",  # Add this
]
```

---

## Using the QCodesStationMixin

The `QCodesStationMixin` provides common qcodes Station functionality:

```python
class QCodesStationMixin:
    """Mixin providing common qcodes Station functionality."""

    QCODES_DRIVER: str = None   # Set to full qcodes driver path
    INSTRUMENT_NAME: str = None  # Set to "awg" or "scope"

    def _init_station(self, config: dict):
        """Initialize qcodes Station from config dict."""
        # Creates temp YAML file and initializes Station

    def _disconnect_station(self):
        """Close Station instruments and cleanup."""
```

### When NOT to Use QCodesStationMixin

If your instrument doesn't use qcodes Station (e.g., uses a different driver framework), you can implement the instrument directly:

```python
@InstrumentRegistry.register_awg("custom_awg")
class CustomAWG(ArbitraryWaveformGenerator):
    """Custom AWG that doesn't use qcodes."""

    def __init__(self, config: dict, **kwargs):
        import custom_driver
        self.driver = custom_driver.connect(config["address"])

    def upload(self, sequence):
        # Custom upload logic
        pass

    def jump_to(self, index: int):
        self.driver.jump(index)

    def trigger(self):
        self.driver.trig()

    def disconnect(self):
        self.driver.close()
```

---

## Abstract Base Class Reference

### ArbitraryWaveformGenerator (AWG)

Required methods to implement:

| Method | Description |
|--------|-------------|
| `upload(sequence)` | Upload a broadbean Sequence to the AWG |
| `jump_to(index)` | Jump to a specific sequence position |
| `trigger()` | Trigger the AWG to start playback |
| `disconnect()` | Clean up and disconnect |

Optional methods (have default implementations):

| Method | Description |
|--------|-------------|
| `trigger_segment(segment)` | Jump to segment and trigger (calls `jump_to` + `trigger`) |
| `upload_sequence(data, name, calibration)` | Parse JSON and call `upload` |
| `upload_sequence_from_json(path, name, calibration)` | Load JSON file and upload |

### Scope

Required methods to implement:

| Method | Description |
|--------|-------------|
| `single()` | Arm scope for single acquisition |
| `download()` | Download acquired waveforms |
| `timebase()` | Get time axis information |
| `disconnect()` | Clean up and disconnect |

---

## Testing Your Implementation

### Basic Test

```python
from broadbean.instruments.registry import InstrumentRegistry

# Test registration
assert "keysight_m8195a" in InstrumentRegistry.get_registered_awg_drivers()

# Test creation (requires hardware or mocked connection)
config = {
    "address": "TCPIP0::192.168.0.10::inst0::INSTR",
    "parameters": {}
}
awg = InstrumentRegistry.create_awg("keysight_m8195a", config)
```

### Mock Testing

For unit tests without hardware, you can create a test mock:

```python
import unittest
from unittest.mock import MagicMock, patch

class TestKeysightM8195A(unittest.TestCase):
    @patch('broadbean.instruments.awg.keysight.Station')
    def test_init(self, mock_station):
        from broadbean.instruments.awg.keysight import KeysightM8195A

        mock_station.return_value.load_awg.return_value = MagicMock()

        config = {"address": "mock", "parameters": {}}
        awg = KeysightM8195A(config)

        self.assertIsNotNone(awg.awg)
```

---

## Troubleshooting

### Driver Not Found

If you see `Unknown AWG driver: 'xxx'`:
1. Check the driver key in your `@InstrumentRegistry.register_awg()` decorator matches what you're using
2. Ensure your module is imported in the package `__init__.py`
3. Verify the import happens before the factory is called (check import order in `broadbean/interface/awg.py`)

### QCodes Station Errors

If qcodes Station fails to load:
1. Verify the `QCODES_DRIVER` path is correct
2. Check that the qcodes driver package is installed
3. Verify the VISA address format is correct for your instrument

### UI Not Showing New Instrument

After adding a new driver:
1. The enum in `registry.py` must include the new key for it to appear in UI dropdowns
2. Run Django migrations if you've changed model defaults
3. Clear browser cache if using the web interface

---

## File Checklist

When adding a new instrument, ensure you've updated:

- [ ] `src/broadbean/instruments/registry.py` - Add driver key to enum
- [ ] `src/broadbean/instruments/awg/<vendor>.py` or `scope/<vendor>.py` - Create implementation
- [ ] `src/broadbean/instruments/awg/__init__.py` or `scope/__init__.py` - Import and export
- [ ] `src/broadbean/instruments/__init__.py` - Export from main package (optional)
- [ ] `src/broadbean/designer/models.py` - Update `to_station_yaml()` mapping if needed

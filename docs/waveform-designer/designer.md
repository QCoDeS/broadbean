# Waveform Designer User Guide

The Waveform Designer is a web-based interface for creating, editing, and managing waveform sequences for arbitrary waveform generators (AWGs) using the broadbean package. It integrates seamlessly with broadbean's pulse building capabilities. It creates a local SQLite database to manage waveforms and instrument configurations.

It also provides an interface to directly upload and trigger waveforms from Tektronix AWG7000x Arbitrary Waveform Generators and capture traces from Tektronix DPO7200x oscilloscopes using the qcodes instrument drivers.

## Installation

Install broadbean with the designer optional dependencies:

```bash
pip install broadbean[designer]
```

For hardware instrument support (Tektronix AWGs/Scopes via qcodes), also install:

```bash
pip install broadbean[designer,hardware]
```

## Starting the Designer

### Command Line

Run the designer server using the `broadbean-designer` command:

```bash
# Start with default settings (http://127.0.0.1:8000/)
broadbean-designer runserver

# Or simply (defaults to runserver)
broadbean-designer

# Specify host and port
broadbean-designer runserver 0.0.0.0:8080

# Run database migrations (first time or after updates)
broadbean-designer migrate
```

Alternatively, use the Python module syntax:

```bash
python -m broadbean.designer.manage runserver
python -m broadbean.designer.manage migrate
```

### From Python

```python
from broadbean.designer import run

# Start the server programmatically (runs migrations automatically)
run(host="127.0.0.1", port=8000)
```

## Features Overview

The designer provides five main interfaces accessible from the navigation bar:

### 1. Designer (Waveform Element Editor)

Create and edit individual waveform elements consisting of multiple channels and segments.

**Supported Segment Types:**
- **Ramp**: Linear transition between start and stop amplitudes
- **Sine**: Sinusoidal waveform with configurable frequency, amplitude, phase, and offset
- **Gaussian**: Gaussian pulse with configurable amplitude, width, and center
- **Exponential**: Rising or decaying exponential
- **Wait Until**: Hold at current value until absolute time
- **Custom**: User-defined function using numpy expressions

**Markers:**
Each segment can have up to 2 markers with configurable delay and duration.

**Workflow:**
1. Set the sample rate and number of channels
2. Add segments to each channel
3. Configure segment parameters
4. Preview the waveform
5. Save as a named element

### 2. Sequencer

Compose saved waveform elements into sequences with sequencing parameters.

**Sequencing Parameters:**
- **Position**: Order in the sequence (1-indexed)
- **Trigger Input**: Which trigger to wait for (0-3)
- **Repetitions**: Number of times to repeat the element
- **Goto**: Next position to jump to after completion
- **Flags**: Per-channel flag settings (A, B, C, D)

**Workflow:**
1. Select saved elements from the library
2. Arrange them in sequence positions
3. Configure sequencing parameters for each position
4. Preview the complete sequence
5. Save the sequence

### 3. Upload & Capture

Upload sequences to AWG hardware and capture scope traces.

**Features:**
- Select AWG and Scope configurations
- Upload saved sequences to the AWG
- Trigger playback and capture scope data
- Jump to specific sequence positions
- Apply LUT (Look-Up Table) calibrations

**Mock Mode:**
When using mock configurations, the designer simulates the AWG→Scope data flow, allowing you to test workflows without hardware.

### 4. Parametric Generator

Generate sequences with parametrically varying elements.

**Use Cases:**
- Amplitude sweeps
- Frequency sweeps
- Duration sweeps
- Multi-parameter sweeps

### 5. Instruments

Configure AWG, Scope, and LUT settings.

**AWG Configuration:**
- Name and description
- VISA address
- Driver type (Mock, Tektronix AWG70001A, AWG70002A)
- Channel parameters (resolution, amplitude, etc.)
- Use flags option

**Scope Configuration:**
- Name and description
- VISA address
- Driver type (Mock, Tektronix DPO70000, DPO7200)
- Acquisition parameters
- Channel settings (coupling, scale, offset)

**LUT Configuration:**
- Create amplitude calibration lookup tables
- Import from CSV files
- Apply to sequences during upload

## Data Storage

The designer uses SQLite for data storage. By default, the database is created at:

```
<broadbean-package-dir>/designer/db.sqlite3
```

### Exporting Data

- **Waveform Elements**: Export as JSON via the Designer interface
- **Sequences**: Download as JSON via the Sequencer interface
- **Configurations**: Download AWG/Scope configs as YAML

## API Endpoints

The designer exposes REST API endpoints for programmatic access:

```
GET  /api/elements/              # List all waveform elements
GET  /api/elements/<id>/         # Get specific element
POST /api/waveform/save/         # Save new element
POST /api/waveform/preview/      # Preview waveform (returns plot data)

GET  /api/sequences/             # List all sequences
GET  /api/sequences/<id>/        # Get specific sequence
POST /api/sequence/save/         # Save new sequence
POST /api/sequence/preview/      # Preview sequence

GET  /api/awg-configs/           # List AWG configurations
GET  /api/scope-configs/         # List Scope configurations
GET  /api/lut-configs/           # List LUT configurations

POST /api/upload-sequence/       # Upload sequence to AWG
POST /api/trigger-and-capture/   # Trigger AWG and capture scope
```

## Troubleshooting

### Server Won't Start

1. Ensure Django is installed: `pip install broadbean[designer]`
2. Run migrations: `broadbean-designer migrate`
3. Check for port conflicts

### Hardware Connection Issues

1. Verify VISA address is correct
2. Ensure NI-VISA or KeySight-VISA is installed
3. Check that qcodes drivers are installed: `pip install broadbean[hardware]`
4. Test with mock configuration first

### Database Errors

Reset the database if needed:

```bash
# Remove old database
rm <path-to>/designer/db.sqlite3

# Run migrations
broadbean-designer migrate
```

## Integration with Broadbean

The designer uses broadbean's core classes internally:

```python
from broadbean import BluePrint, Element, Sequence

# Designer creates these objects from the UI
# and can export sequences as JSON

# You can also load designer-created sequences programmatically:
import json
from broadbean.sequence import Sequence

with open("my_sequence.json") as f:
    data = json.load(f)

seq = Sequence.sequence_from_description(data)
```

## See Also

- [Adding New Instruments](adding-new-instruments.md) - How to add support for new AWG/Scope hardware
- [Broadbean Examples](../examples/index.rst) - Example notebooks for pulse building

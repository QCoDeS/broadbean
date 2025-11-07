# Test suite for the plotting module of the broadbean package

import matplotlib
import pytest

matplotlib.use("Agg")  # Use non-interactive backend for tests
import matplotlib.figure

import broadbean as bb
from broadbean.plotting import plotter


@pytest.fixture
def simple_blueprint():
    """
    Create a simple blueprint for testing
    """
    bp = bb.BluePrint()
    bp.insertSegment(0, bb.PulseAtoms.ramp, args=(0, 1), name="rise", dur=1e-6)
    bp.insertSegment(1, bb.PulseAtoms.ramp, args=(1, 0), name="fall", dur=1e-6)
    bp.setSR(1e9)
    return bp


@pytest.fixture
def simple_element():
    """
    Create a simple element for testing
    """
    bp = bb.BluePrint()
    bp.insertSegment(0, bb.PulseAtoms.ramp, args=(0, 1), name="ramp", dur=1e-6)
    bp.setSR(1e9)

    elem = bb.Element()
    elem.addBluePrint(1, bp)
    return elem


@pytest.fixture
def simple_sequence():
    """
    Create a simple sequence for testing
    """
    bp1 = bb.BluePrint()
    bp1.insertSegment(0, bb.PulseAtoms.ramp, args=(0, 1), name="rise", dur=1e-6)
    bp1.setSR(1e9)

    bp2 = bb.BluePrint()
    bp2.insertSegment(0, bb.PulseAtoms.ramp, args=(1, 0), name="fall", dur=1e-6)
    bp2.setSR(1e9)

    elem1 = bb.Element()
    elem1.addBluePrint(1, bp1)

    elem2 = bb.Element()
    elem2.addBluePrint(1, bp2)

    seq = bb.Sequence()
    seq.addElement(1, elem1)
    seq.addElement(2, elem2)
    seq.setSR(1e9)

    return seq


@pytest.fixture
def blueprint_with_markers():
    """
    Create a blueprint with markers for testing
    """
    bp = bb.BluePrint()
    bp.insertSegment(0, bb.PulseAtoms.ramp, args=(0, 1), name="rise", dur=1e-6)
    bp.insertSegment(1, bb.PulseAtoms.ramp, args=(1, 0), name="fall", dur=1e-6)
    bp.setSR(1e9)

    # Add markers
    bp.marker1 = [(0, 0.5e-6)]
    bp.marker2 = [(1e-6, 0.5e-6)]

    return bp


##################################################
# TEST BACKEND PARAMETER VALIDATION


def test_plotter_invalid_backend(simple_blueprint):
    """Test that invalid backend raises ValueError"""
    with pytest.raises(ValueError, match="Invalid backend"):
        plotter(simple_blueprint, backend="invalid")


def test_plotter_matplotlib_backend_default(simple_blueprint):
    """Test that matplotlib is the default backend"""
    fig = plotter(simple_blueprint)
    assert isinstance(fig, matplotlib.figure.Figure)


def test_plotter_matplotlib_backend_explicit(simple_blueprint):
    """Test explicit matplotlib backend selection"""
    fig = plotter(simple_blueprint, backend="matplotlib")
    assert isinstance(fig, matplotlib.figure.Figure)


##################################################
# TEST MATPLOTLIB BACKEND


def test_matplotlib_blueprint(simple_blueprint):
    """Test matplotlib plotting of a blueprint"""
    fig = plotter(simple_blueprint, backend="matplotlib")
    assert isinstance(fig, matplotlib.figure.Figure)
    assert len(fig.axes) == 1  # 1 channel, 1 position


def test_matplotlib_element(simple_element):
    """Test matplotlib plotting of an element"""
    fig = plotter(simple_element, backend="matplotlib")
    assert isinstance(fig, matplotlib.figure.Figure)
    # 1 channel subplot + 1 twin axis for channel label
    assert len(fig.axes) >= 1


def test_matplotlib_sequence(simple_sequence):
    """Test matplotlib plotting of a sequence"""
    fig = plotter(simple_sequence, backend="matplotlib")
    assert isinstance(fig, matplotlib.figure.Figure)
    # 1 channel, 2 positions + 1 twin axis for channel label
    assert len(fig.axes) >= 2


def test_matplotlib_with_markers(blueprint_with_markers):
    """Test matplotlib plotting with markers"""
    elem = bb.Element()
    elem.addBluePrint(1, blueprint_with_markers)

    fig = plotter(elem, backend="matplotlib")
    assert isinstance(fig, matplotlib.figure.Figure)
    # Should have plotted the waveform and markers
    ax = fig.axes[0]
    assert len(ax.lines) > 1  # Waveform + marker lines


##################################################
# TEST PLOTLY BACKEND


def test_plotly_import_error(simple_blueprint, monkeypatch):
    """Test that missing plotly raises helpful ImportError"""

    def mock_import(name, *args, **kwargs):
        if "plotly" in name:
            raise ImportError("No module named 'plotly'")
        return __import__(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", mock_import)

    with pytest.raises(ImportError, match="plotly is required"):
        plotter(simple_blueprint, backend="plotly")


@pytest.mark.skipif(
    not pytest.importorskip("plotly", reason="plotly not installed"),
    reason="plotly not available",
)
def test_plotly_blueprint():
    """Test plotly plotting of a blueprint"""
    import plotly.graph_objects as go

    bp = bb.BluePrint()
    bp.insertSegment(0, bb.PulseAtoms.ramp, args=(0, 1), name="rise", dur=1e-6)
    bp.setSR(1e9)

    fig = plotter(bp, backend="plotly")
    assert isinstance(fig, go.Figure)
    # Check that traces were added
    assert len(fig.data) > 0


@pytest.mark.skipif(
    not pytest.importorskip("plotly", reason="plotly not installed"),
    reason="plotly not available",
)
def test_plotly_element():
    """Test plotly plotting of an element"""
    import plotly.graph_objects as go

    bp = bb.BluePrint()
    bp.insertSegment(0, bb.PulseAtoms.ramp, args=(0, 1), name="rise", dur=1e-6)
    bp.setSR(1e9)

    elem = bb.Element()
    elem.addBluePrint(1, bp)

    fig = plotter(elem, backend="plotly")
    assert isinstance(fig, go.Figure)
    assert len(fig.data) > 0


@pytest.mark.skipif(
    not pytest.importorskip("plotly", reason="plotly not installed"),
    reason="plotly not available",
)
def test_plotly_sequence():
    """Test plotly plotting of a sequence"""
    import plotly.graph_objects as go

    bp1 = bb.BluePrint()
    bp1.insertSegment(0, bb.PulseAtoms.ramp, args=(0, 1), name="rise", dur=1e-6)
    bp1.setSR(1e9)

    bp2 = bb.BluePrint()
    bp2.insertSegment(0, bb.PulseAtoms.ramp, args=(1, 0), name="fall", dur=1e-6)
    bp2.setSR(1e9)

    elem1 = bb.Element()
    elem1.addBluePrint(1, bp1)

    elem2 = bb.Element()
    elem2.addBluePrint(1, bp2)

    seq = bb.Sequence()
    seq.addElement(1, elem1)
    seq.addElement(2, elem2)
    seq.setSR(1e9)

    fig = plotter(seq, backend="plotly")
    assert isinstance(fig, go.Figure)
    assert len(fig.data) > 0


@pytest.mark.skipif(
    not pytest.importorskip("plotly", reason="plotly not installed"),
    reason="plotly not available",
)
def test_plotly_with_markers():
    """Test plotly plotting with markers"""
    import plotly.graph_objects as go

    bp = bb.BluePrint()
    bp.insertSegment(0, bb.PulseAtoms.ramp, args=(0, 1), name="rise", dur=1e-6)
    bp.insertSegment(1, bb.PulseAtoms.ramp, args=(1, 0), name="fall", dur=1e-6)
    bp.setSR(1e9)

    # Add markers
    bp.marker1 = [(0, 0.5e-6)]
    bp.marker2 = [(1e-6, 0.5e-6)]

    elem = bb.Element()
    elem.addBluePrint(1, bp)

    fig = plotter(elem, backend="plotly")
    assert isinstance(fig, go.Figure)
    # Should have multiple traces (waveform + markers)
    assert len(fig.data) > 1


@pytest.mark.skipif(
    not pytest.importorskip("plotly", reason="plotly not installed"),
    reason="plotly not available",
)
def test_plotly_multichannel():
    """Test plotly plotting with multiple channels"""
    import plotly.graph_objects as go

    bp1 = bb.BluePrint()
    bp1.insertSegment(0, bb.PulseAtoms.ramp, args=(0, 1), name="rise", dur=1e-6)
    bp1.setSR(1e9)

    bp2 = bb.BluePrint()
    bp2.insertSegment(0, bb.PulseAtoms.ramp, args=(1, 0), name="fall", dur=1e-6)
    bp2.setSR(1e9)

    elem = bb.Element()
    elem.addBluePrint(1, bp1)
    elem.addBluePrint(2, bp2)

    fig = plotter(elem, backend="plotly")
    assert isinstance(fig, go.Figure)
    # Should have traces for both channels
    assert len(fig.data) > 0


@pytest.mark.skipif(
    not pytest.importorskip("plotly", reason="plotly not installed"),
    reason="plotly not available",
)
def test_plotly_layout_properties():
    """Test that plotly figure has correct layout properties"""
    import plotly.graph_objects as go

    bp = bb.BluePrint()
    bp.insertSegment(0, bb.PulseAtoms.ramp, args=(0, 1), name="rise", dur=1e-6)
    bp.setSR(1e9)

    fig = plotter(bp, backend="plotly")
    assert isinstance(fig, go.Figure)

    # Check layout properties
    assert fig.layout.plot_bgcolor == "white"
    assert fig.layout.paper_bgcolor == "white"
    assert fig.layout.showlegend is False


##################################################
# TEST BACKEND CONSISTENCY


@pytest.mark.skipif(
    not pytest.importorskip("plotly", reason="plotly not installed"),
    reason="plotly not available",
)
def test_backends_produce_output():
    """Test that both backends produce output without errors"""
    bp = bb.BluePrint()
    bp.insertSegment(0, bb.PulseAtoms.ramp, args=(0, 1), name="rise", dur=1e-6)
    bp.setSR(1e9)

    elem = bb.Element()
    elem.addBluePrint(1, bp)

    # Both should complete without errors
    fig_mpl = plotter(elem, backend="matplotlib")
    fig_plotly = plotter(elem, backend="plotly")

    assert fig_mpl is not None
    assert fig_plotly is not None


##################################################
# TEST FORGER KWARGS


def test_matplotlib_with_forger_kwargs(simple_element):
    """Test that forger kwargs are passed through for matplotlib"""
    fig = plotter(simple_element, backend="matplotlib", apply_delays=False)
    assert isinstance(fig, matplotlib.figure.Figure)


@pytest.mark.skipif(
    not pytest.importorskip("plotly", reason="plotly not installed"),
    reason="plotly not available",
)
def test_plotly_with_forger_kwargs():
    """Test that forger kwargs are passed through for plotly"""
    import plotly.graph_objects as go

    bp = bb.BluePrint()
    bp.insertSegment(0, bb.PulseAtoms.ramp, args=(0, 1), name="rise", dur=1e-6)
    bp.setSR(1e9)

    elem = bb.Element()
    elem.addBluePrint(1, bp)

    fig = plotter(elem, backend="plotly", apply_delays=False)
    assert isinstance(fig, go.Figure)

## Broadbean aka QCoDeS Pulse Builder

[ ![PyPi](https://badge.fury.io/py/broadbean.svg) ](https://badge.fury.io/py/broadbean)
[ ![Build Status Github Docs](https://github.com/QCoDeS/broadbean/workflows/build%20docs/badge.svg) ](https://github.com/QCoDeS/broadbean/actions?query=workflow%3A%22build+docs%22)
[ ![DOCS](https://img.shields.io/badge/read%20-thedocs-ff66b4.svg) ](https://qcodes.github.io/broadbean/index.html#)
[ ![PyPI python versions](https://img.shields.io/pypi/pyversions/broadbean.svg) ](https://pypi.python.org/pypi/broadbean/)
[ ![Build Status Github](https://github.com/QCoDeS/broadbean/workflows/Run%20mypy%20and%20pytest/badge.svg) ](https://github.com/QCoDeS/broadbean/actions?query=workflow%3A%22Run+mypy+and+pytest%22)

A library for making pulses that can be leveraged with QCoDeS (in
particular with Tektronix 5000/7000 series AWG drivers),
but also works as standalone.

Usage examples can be found in broadbean's documentation [here](https://qcodes.github.io/broadbean/examples/index.html).

Short description: The broadbean module lets the user compose and
manipulate pulse sequences. The aim of the module is to reduce pulse
building to the logical minimum of specifications so that building and
manipulation become as easy as saying "Gimme a square wave, then a
ramp, then a sine, and then wait for 10 ms" and, in particular, "Do
the same thing again, but now with the sine having twice the frequency
it had before".

The little extra module called `ripasso` performs frequency filtering
and frequency filter  compensation. It could be useful in a general
setting and is therefore factored out to its own module.

The name: The broad bean is one of my favourite pulses.

### Formal requirements

The broadbean package only works with python 3.9+

### Installation
In general, refer to [broadbeans documentation](https://qcodes.github.io/broadbean/start/index.html#installation)
for installation instructions.

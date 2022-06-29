## Broadbean aka QCoDeS Pulse Builder

[ ![PyPi](https://badge.fury.io/py/broadbean.svg) ](https://badge.fury.io/py/broadbean)
[ ![DOCS](https://readthedocs.org/projects/broadbean/badge/?version=latest) ](http://broadbean.readthedocs.io/en/latest/?badge=latest)
[ ![PyPI python versions](https://img.shields.io/pypi/pyversions/broadbean.svg) ](https://pypi.python.org/pypi/broadbean/)
[ ![Build Status Github](https://github.com/QCoDeS/broadbean/workflows/Run%20mypy%20and%20pytest/badge.svg) ](https://github.com/QCoDeS/broadbean/actions?query=workflow%3A%22Run+mypy+and+pytest%22)

A library for making pulses that can be leveraged with QCoDeS (in
particular its Tektronix AWG 5014 driver), but also works as standalone.

The usage is documented in example notebooks TODO: add link to hosted docs.

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

The broadbean package only works with python 3.7+

### Installation

TODO: add link to installation from docs

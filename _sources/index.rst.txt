.. broadbean documentation master file, created by
   sphinx-quickstart on Wed May 17 09:11:27 2017.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to broadbean's documentation!

The broadbean package is a tool for creating and manipulating pulse
sequences.The broadbean module lets the user compose and manipulate pulse sequences.
The aim of the module is to reduce pulse building to the logical minimum of
specifications so that building and manipulation become as easy as saying "Gimme
a square wave, then a ramp, then a sine, and then wait for 10 ms" and, in particular,
"Do the same thing again, but now with the sine having twice the frequency it had before".

The little extra module called ripasso performs frequency filtering and frequency filter
compensation. It could be useful in a general setting and is therefore factored out
to its own module.

The name: The broad bean is one of my favourite pulses.


Documentation
-------------

.. toctree::
    :maxdepth: 2

    api/generated/broadbean
    start/index
    examples/index
    changes/index


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

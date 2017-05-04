## QCoDeS Pulsebuilder aka broadbean

A library for making pulses. Supposed to be used with QCoDeS (in
particular its Tektronix AWG 5014 driver), but works as standalone.

The usage is documented in the notebooks.

Current status: The notebooks in `docs` are
the correct and up-to-date ones. All other notebooks are wrong and
obsolete.

Short description: The broadbean module lets the user compose and
manipulate pulse sequences. The aim of the module is to reduce pulse
building to the logical minimum of specifications so that building and
manipulation become as easy as saying "Gimme a square wave, then a
ramp, then a sine, and then wait for 10 ms" and, in particular, "Do
the same thing again, but now with the sine having twice the frequency
it had before".

The name: The broad bean is one of my favourite pulses.

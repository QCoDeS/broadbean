from setuptools import setup

setup(
    name='broadbean',
    version='0.9',

    # We might as well require what we know will work
    # although older numpy and matplotlib version will probably work too
    install_requires=['numpy>=1.12.1',
                      'matplotlib>=2.0.1',
                      'PyQt5>5.7.1'],

    author='William H.P. Nielsen',
    author_email='whpn@mailbox.org',

    description=("Package for easily generating and manipulating signal "
                 "pulses. Developed for use with qubits in the quantum "
                 "computing labs of Copenhagen, Delft, and Sydney, but "
                 "should be generally useable."),

    license='MIT',

    packages=['broadbean'],

    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Science/Research',
        'Programming Language :: Python :: 3.5'
        ],

    keywords='Pulsebuilding signal processing arbitrary waveforms',

    url='https://github.com/QCoDeS/broadbean'
    )

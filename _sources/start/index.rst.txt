.. _gettingstarted:

Getting Started
===============

.. toctree::
   :maxdepth: 2


Requirements
------------

You need a working ``python 3.7`` installation, as the minimum Python version (at present,
we recommend ``python 3.10``), to be able to use ``broadbean``. We highly recommend installing
Miniconda, which takes care of installing Python and managing packages. In the following
it will be assumed that you use Miniconda. Download and install it from `here <https://docs.conda.io/en/latest/miniconda.html>`_.
Make sure to download the latest version with ``python 3.10``.

Once you download, install Miniconda according to the instructions on screen,
choosing the single user installation option.

The next section will guide you through the installation of broadbean on Windows.


Installation
------------
Before you install broadbean you have to decide whether you want to install the
latest stable published release or if you want to get the latest developer version
from broadbean repository on Azure Devops. To install the official package you will need to
configure your computer

Create a broadbean environment
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

As mentioned above, it is recommended to use ``broadbean`` from a ``conda`` environment.
We create that by executing the following command:

.. code:: bash

    conda create -n broadbean-env python=3.10

This will create a python 3.9 environment named broadbean-env.
Once the environment is created close your shell and open it again to ensure that changes take effect.


Installing the latest broadbean release
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The ``broadbean`` package can be installed using pip:

.. code:: bash

    conda activate broadbean-env
    pip install broadbean


Setting up your development environment
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The default ``broadbean`` installation does not include packages such as ``pytest`` that are required for testing and development.
For development and testing, install ``broadbean`` with the ``test`` feature.
Note that ``broadbean`` requires ``python v3.7``, so be sure to include that option when creating your new development environment.
If you run ``broadbean`` from Jupyter notebooks, you may also need to install ``jupyter`` into the development environment.

.. code:: bash

    conda create -n broadbean-development python=3.10
    conda activate broadbean-development
    cd <path to broadbean repository>
    pip install -e .[test]

Updating Broadbean
~~~~~~~~~~~~~~~~~~

If you have installed ``broadbean`` with ``pip``, run the following to update:

.. code:: bash

   pip install --upgrade broadbean

Updates to ``broadbean`` are quite frequent, so please check regularly.

If you have installed ``broadbean`` from the cloned ``git`` repository, pull the ``broadbean``
repository using your favorite method (git bash, git shell, github desktop, ...).

Keeping your environment up to date
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Dependencies are periodically been adjusted for ``broadbean`` (and for ``qcodes``, which ``broadbean`` is built upon)
and new versions of packages that ``broadbean`` depends on get released.
Conda/Miniconda itself is also being updated.

Hence, to keep the broadbean conda environment up to date, please run for the activated broadbean environment:

.. code:: bash

   conda update -n base conda -c defaults
   conda env update

The first line ensures that the ``conda`` package manager it self is
up to date, and the second line will ensure that the latest versions of the
packages used by ``broadbean`` are installed. See
`here <https://conda.io/docs/commands/env/conda-env-update.html>`__ for more
documentation on ``conda env update``.

If you are using broadbean from an editable install, you should also reinstall ``broadbean``
before upgrading the environment to make sure that dependencies are tracked correctly using:

.. code:: bash

    pip uninstall broadbean
    pip install -e <path-to-repository>

Note that if you install packages yourself into the same
environment it is preferable to install them using ``conda``. There is a chance that
mixing packages from ``conda`` and ``pip`` will produce a broken environment,
especially if the same package is installed using both ``pip`` and ``conda``.


Using broadbean
---------------
For using broadbean, as with any other python library, it is useful to use an
application that facilitates the editing and execution of python files. Some
options are:

 - **Jupyter**, a browser based notebook
 - **Vscode**, IDE with ipython capabilities
 - **Spyder**, an integrated development environment

For other options you can launch a terminal either via the *Anaconda Navigator*
by selecting *broadbean* in the *Environments tab* and left-clicking on the *play*
button or by entering

.. code:: bash

    activate broadbean

in the *Anaconda prompt*.

From the terminal you can then start any other application, such as *IPython* or
just plain old *Python*.

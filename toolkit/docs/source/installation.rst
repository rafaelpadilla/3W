============
Installation
============

This guide covers the prerequisites and step-by-step instructions for installing **ThreeWToolkit**.

It is possible to perform the installation in different ways, depending on what you want to do:

- **Just want to use the 3W Toolkit?** Install the published package from PyPI. You don't need to clone the repository.
- **Want to develop or contribute to the 3W Toolkit?** Clone (or fork) the repository and install it locally in editable mode, so your changes are picked up immediately without reinstalling.

Prerequisites
=============

Ensure your environment meets the following baseline requirements:

* **Python**: Version 3.10 or higher.
* **Operating System**: Linux, macOS, or Windows (64-bit).
* **Package Manager**: ``pip``, ``conda``, or ``uv`` (recommended for fast dependency resolution).

Direct Installation via PyPI
============================

The simplest and recommended way for end users to install the latest released version of **ThreeWToolkit** is directly via ``pip``:

.. include:: ../../ThreeWToolkit/README.md
   :parser: myst_parser.sphinx_
   :start-after: <!-- start-installation-opt-a -->
   :end-before: <!-- end-installation-opt-a -->

Development Installation (Source)
=================================

If you plan to contribute to the package, access the latest features on the development branch, or run experimental pipelines, install the toolkit from source in editable mode.

1. Fork or Clone the Repository
--------------------------------

Option A: Clone Official Repository
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Using SSH:

.. code-block:: bash

   git clone git@github.com:petrobras/3W.git
   cd 3W/toolkit/ThreeWToolkit

Using HTTPS:

.. code-block:: bash

   git clone https://github.com/petrobras/3W.git
   cd 3W/toolkit/ThreeWToolkit

Option B: Fork and Clone
~~~~~~~~~~~~~~~~~~~~~~~~

1. Go to `https://github.com/petrobras/3W <https://github.com/petrobras/3W>`_ and click **Fork**.
2. Clone your personal fork locally:

.. code-block:: bash

   git clone git@github.com:<your-username>/3W.git
   cd 3W/toolkit/ThreeWToolkit

2. Install in Editable Mode
---------------------------

.. include:: ../../ThreeWToolkit/README.md
   :parser: myst_parser.sphinx_
   :start-after: <!-- start-installation-editable -->
   :end-before: <!-- end-installation-editable -->

Verifying the Installation
==========================

Verify that the installation was successful by checking the package version in Python:

.. code-block:: python

   import ThreeWToolkit

   print(ThreeWToolkit.__version__)
.. cldflex documentation master file, created by
   sphinx-quickstart on Sat Apr  2 22:11:17 2022.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

cldflex 
========

.. toctree::
   :maxdepth: 2
   :caption: Contents:


Many descriptive linguists have annotated language data in a FLEx (`SIL's Fieldworks Lexical Explorer <https://software.sil.org/fieldworks/>`_) database.
This project aims to build a bridge between said data and the `CLDF standard <https://cldf.clld.org/>`_.
It provides commands to convert `.flextext` (corpora) and `.lift` (lexica) files to `CSV <https://en.wikipedia.org/wiki/Comma-separated_values>`_ files.
CSV files are much easier to process than the formats exportable from FLEx, for many purposes: working with a spreadsheet app, reading them into a dataframe in `R <https://www.r-project.org/>`_ or `pandas <https://pandas.pydata.org/>`_, etc.
They are also readily available for use with `cldfbench <https://github.com/cldf/cldfbench>`_; however, ``cldflex`` also allows for (simple) CLDF creation out of the box.

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

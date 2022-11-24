.. cldflex documentation master file, created by
   sphinx-quickstart on Sat Apr  2 22:11:17 2022.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

cldflex 
========

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   lift2csv.md

Many descriptive linguists have annotated language data in a FLEx (`SIL's Fieldworks Lexical Explorer <https://software.sil.org/fieldworks/>`_) database, perhaps the most popular and accessible assisted segmentation and annotation workflow.
However, a reasonably complete data export is only available in XML, which is not human-friendly, and is not readily converted to other data.
A data format growing in popularity is the `CLDF standard <https://cldf.clld.org/>`_, a table-based approach with human-readable datasets, designed to be used in `CLLD <https://clld.org/>`_ apps and easily processable by any software that can read `CSV <https://en.wikipedia.org/wiki/Comma-separated_values>`_ files, including `R <https://www.r-project.org/>`_, `pandas <https://pandas.pydata.org/>`_, or spreadsheet applications.

The goal of ``cldflex`` is to convert lexicon and corpus data stored in FLEx to CSV tables, primarily for use in CLDF datasets.
At the moment, it has two commands: ``cldflex flex2csv`` processes `.flextext` (corpora), and ``cldflex lift2csv`` processes `.lift` (lexica) files.
Then, one can either use `cldfbench <https://github.com/cldf/cldfbench>`_ to create one's own CLDF datasets, or use the ``cldflex``' built-in workflows to create (simple) datasets.

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

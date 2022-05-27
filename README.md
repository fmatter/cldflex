# cldflex

Convert FLEx data to CLDF-ready CSV.

![License](https://img.shields.io/github/license/fmatter/cldflex)
[![Documentation Status](https://readthedocs.org/projects/cldflex/badge/?version=latest)](https://cldflex.readthedocs.io/en/latest/?badge=latest)
![Build Status](https://img.shields.io/github/workflow/status/fmatter/cldflex/tests)
[![Codecov](https://img.shields.io/codecov/c/github/fmatter/cldflex)](https://app.codecov.io/gh/fmatter/cldflex/)
[![PyPI](https://img.shields.io/pypi/v/cldflex.svg)](https://pypi.org/project/cldflex)
![Versions](https://img.shields.io/pypi/pyversions/cldflex)

* Documentation: https://cldflex.readthedocs.io

This package provides several command line hooks:

### `lift2csv`
Export your lexicon in lift format, then use `lift2csv /path/to/your/lexicon_file.lift` to convert it to a csv file with the following structure:

**ID**|**Language\_ID**|**Form**|**Meaning**
:-----:|:-----:|:-----:|:-----:
FLEx-internal hash|ISO code|"; "-delimited allomorphs|translation
…|…|…|…

### `flex2cldf`
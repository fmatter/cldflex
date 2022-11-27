# cldflex

Convert FLEx data to CLDF-ready CSV.

![License](https://img.shields.io/github/license/fmatter/cldflex)
[![Tests](https://img.shields.io/github/workflow/status/fmatter/cldflex/tests?label=tests)](https://github.com/fmatter/cldflex/actions/workflows/tests.yml)
[![Linting](https://img.shields.io/github/workflow/status/fmatter/cldflex/lint?label=linting)](https://github.com/fmatter/cldflex/actions/workflows/lint.yml)
[![Codecov](https://img.shields.io/codecov/c/github/fmatter/cldflex)](https://app.codecov.io/gh/fmatter/cldflex/)
[![PyPI](https://img.shields.io/pypi/v/cldflex.svg)](https://pypi.org/project/cldflex)
![Versions](https://img.shields.io/pypi/pyversions/cldflex)

Many descriptive linguists have annotated language data in a FLEx ([SIL's Fieldworks Lexical Explorer](https://software.sil.org/fieldworks/)) database, perhaps the most popular and accessible assisted segmentation and annotation workflow.
However, a reasonably complete data export is only available in XML, which is not human-friendly, and is not readily converted to other data.
A data format growing in popularity is the [CLDF standard](https://cldf.clld.org/), a table-based approach with human-readable datasets, designed to be used in [CLLD](https://clld.org/) apps and easily processable by any software that can read [CSV](https://en.wikipedia.org/wiki/Comma-separated_values) files, including  [R](https://www.r-project.org/), [pandas](https://pandas.pydata.org/) or spreadsheet applications.
The goal of ``cldflex`` is to convert lexicon and corpus data stored in FLEx to CSV tables, primarily for use in CLDF datasets.

## Installation

`cldflex` is available on [PyPI](https://pypi.org/project/cldflex):
```shell
pip install cldflex
```
## Usage
At the moment, there are two commands: ``cldflex flex2csv`` processes `.flextext` (corpora), and ``cldflex lift2csv`` processes `.lift` (lexica) files.
Both commands create a number of CSV files.
One can either use [cldfbench](https://github.com/cldf/cldfbench) to create one's own CLDF datasets from these files, or add the `--cldf` argument to create (simple) datasets.

Project-specific configuration can be passed via `--conf your/config.yaml`

### `flex2csv`
Basic usage:

```shell
cldflex flex2csv texts.flextext
```

Connect the corpus with the lexicon:

```shell
cldflex flex2csv texts.flextext --lexicon lexicon.lift
```

Create a CLDF dataset:

```shell
cldflex flex2csv texts.flextext --lexicon lexicon.lift --cldf
```

### `lift2csv`

Extract morphemes, morphs, and entries from `lexicon.lift`:

```shell
cldflex lift2csv lexicon.lift
```

Create a CLDF dataset with a  [`Dictionary`](https://github.com/cldf/cldf/tree/master/modules/Dictionary) module:

```shell
cldflex lift2csv lexicon.lift --cldf
```
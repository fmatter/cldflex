# cldflex

Convert FLEx data to CLDF-ready CSV.

[![Versions](https://img.shields.io/pypi/pyversions/clld_morphology_plugin)](https://www.python.org/)
[![PyPI](https://img.shields.io/pypi/v/clld_morphology_plugin.svg)](https://pypi.org/project/clld_morphology_plugin)
[![License](https://img.shields.io/github/license/fmatter/cldflex)](https://www.apache.org/licenses/LICENSE-2.0)


Many descriptive linguists have annotated language data in a FLEx ([SIL's Fieldworks Lexical Explorer](https://software.sil.org/fieldworks/)) database, which provides perhaps the most popular and accessible assisted segmentation and annotation workflow.
However, a reasonably complete data export is only available in XML, which is not human-friendly, and is not readily converted to other data.
A data format growing in popularity is the [CLDF standard](https://cldf.clld.org/), a table-based approach with human-readable datasets, designed to be used in [CLLD](https://clld.org/) apps and easily processable by any software that can read [CSV](https://en.wikipedia.org/wiki/Comma-separated_values) files, including  [R](https://www.r-project.org/), [pandas](https://pandas.pydata.org/) or spreadsheet applications.
The goal of ``cldflex`` is to convert lexicon and corpus data stored in FLEx to CSV tables, primarily for use in CLDF datasets.

## Installation

`cldflex` is available on [PyPI](https://pypi.org/project/cldflex):
```shell
pip install cldflex
```

## Command line usage
At the moment, there are three commands: ``cldflex corpus`` for `.flextext` files; ``cldflex dictionary`` and `cldflex wordlist` for `.lift` files.
All commands create a number of CSV files.
One can either use [cldfbench](https://github.com/cldf/cldfbench) to create one's own CLDF datasets from these files, or add the `--cldf` argument to create a simple CLDF dataset.
Project-specific [configuration](#configuration) can be passed by `--conf your/config.yaml`, or creating a file `cldflex.yaml`

### `corpus`
Basic usage:

```shell
cldflex corpus texts.flextext
```

Connect the corpus with the lexicon:

```shell
cldflex corpus texts.flextext --lexicon lexicon.lift
```

Create a CLDF dataset:

```shell
cldflex corpus texts.flextext --lexicon lexicon.lift --cldf
```

### `dictionary`

Extract morphemes, morphs, and entries from `lexicon.lift`:

```shell
cldflex dictionary lexicon.lift
```

Create a CLDF dataset with a  [`Dictionary`](https://github.com/cldf/cldf/tree/master/modules/Dictionary) module:

```shell
cldflex dictionary lexicon.lift --cldf
```

### `wordlist`

Create a CLDF dataset with a  [`Wordlist`](https://github.com/cldf/cldf/tree/master/modules/Wordlist) module:

```shell
cldflex wordlist lexicon.lift --cldf
```

## API usage
The functions corresponding to the commands above are [`cldflex.corpus.convert()`](https://github.com/fmatter/cldflex/blob/4d9962ff53baab68a20ecce34f8623e87f7197ec/src/cldflex/corpus.py#L445) and [`cldflex.lift2csv.convert()`](https://github.com/fmatter/cldflex/blob/4d9962ff53baab68a20ecce34f8623e87f7197ec/src/cldflex/lift2csv.py#L130).

## Configuration
There is no default configuration.
Rather, `cldflex` will guess values for most of the parameters below and tell you what it's doing.
It is suggested to start out configuration-free until something goes wrong or you want to change something.
Create a [YAML](https://yaml.org/) file for CLI usage, pass a dict to the `convert` methods.

* `obj_lg`: the object language
* `gloss_lg`: the language used for glossing / translation
* `msa_lg`: the language used for storing POS information
* `lang_id`: the value to be used in the created tables
* `glottocode`: used to look up language metadata from glottolog
* `csv_cell_separator`: if there are multiple values in a cell (allomorphs, polysemy...), they are by default separated by `"; "`
* `form_slices`: set to `false` if you don't want form slices connecting morphs and word forms
* `mappings`: a dictionary specifying name changes of columns in the created CSV files
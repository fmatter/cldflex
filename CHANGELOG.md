# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## Added
* CLDF dataset creation
* `senses.csv`

## Fixed
* lexicon retrieval of clitics
* path handling in CLI

## Changed
* re-reimplemented XML extraction

## [0.0.3] -- 2022-10-22

## Fixed
* missing glosses are handled
* all records make it into `sentences.csv`
* empty fields in produced lexicon csv file are handled

## Changed
* reimplemented `flex2csv` and `lift2csv` from the ground up with `beautifulsoup`

## [0.0.2] - 2022-10-17

### Added
* skip LIFT entries without sense(s)
* check for either `gloss` or `definition` in senses

### Changed
* overhaul of `flex2csv` component
* more informative and colorful log

## [0.0.1] - 2022-03-08

Initial release

[Unreleased]: https://github.com/fmatter/cldflex/compare/v0.0.3...HEAD
[0.0.3]: https://github.com/fmatter/cldflex/releases/tag/v0.0.3
[0.0.2]: https://github.com/fmatter/cldflex/releases/tag/v0.0.2
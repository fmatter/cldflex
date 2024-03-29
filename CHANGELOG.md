# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.1] - 2023-11-06

### Added
* option to add audio files
* `wordlist` command
 
### Fixed
* gracefully handle clitics annotated as separate words
* handle empty translations in dic examples

### Changed
* now generating tables for lexemes, stems, morphemes, morphs, using [cldf-ldd](https://github.com/fmatter/cldf-ldd/) for the CLDF side
* externalized `morph_id` retrieval
* deleting existing columns when renaming
* use `drop_empty` in `cldf` settings to omit empty senses when converting LIFT
* renamed commands

## [0.1.0] - 2022-11-27

### Fixed
* lexicon retrieval of clitics
* path handling in CLI

### Changed
* re-reimplemented XML extraction

### Added
* CLDF dataset creation
* `senses.csv`

## [0.0.3] -- 2022-10-22

### Fixed
* missing glosses are handled
* all records make it into `sentences.csv`
* empty fields in produced lexicon csv file are handled

### Changed
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

[Unreleased]: https://github.com/fmatter/cldflex/compare/v0.1.1...HEAD
[0.1.1]: https://github.com/fmatter/cldflex/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/fmatter/cldflex/compare/v0.0.3...v0.1.0
[0.0.3]: https://github.com/fmatter/cldflex/releases/tag/v0.0.3
[0.0.2]: https://github.com/fmatter/cldflex/releases/tag/v0.0.2
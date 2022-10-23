# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## Fixed
* missing glosses are handled
* all records make it into `sentences.csv`

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

[Unreleased]: https://github.com/fmatter/cldflex/compare/v0.0.2...HEAD
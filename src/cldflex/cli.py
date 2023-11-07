"""Console script for cldflex."""
import sys
from pathlib import Path

import click
from writio import load

from cldflex.flex2csv import convert as flex2csv_convert
from cldflex.lift2csv import convert as lift2csv_convert


def _load_config(config_file):
    if not config_file:
        if Path("cldflex.yaml").is_file():
            return load("cldflex.yaml")
        return None
    return load(config_file)


@click.group()
def main():
    pass  # pragma: no cover


@main.command()
@click.argument("filename", type=click.Path(exists=True, path_type=Path))
@click.option(
    "-c",
    "--conf",
    "config_file",
    type=click.Path(exists=True, path_type=Path),
    default=None,
)
@click.option(
    "-o",
    "--output",
    "output_dir",
    type=click.Path(exists=True, path_type=Path),
    default=None,
)
@click.option("-d", "--cldf", "cldf", default=False, is_flag=True)
def dictionary(filename, config_file, cldf, output_dir):
    if not output_dir:
        output_dir = Path(filename.parents[0])
    lift2csv_convert(
        filename,
        conf=_load_config(config_file),
        cldf=cldf,
        output_dir=output_dir,
        cldf_mode="dictionary",
    )


@main.command()
@click.argument("filename", type=click.Path(exists=True, path_type=Path))
@click.option(
    "-c",
    "--conf",
    "config_file",
    type=click.Path(exists=True, path_type=Path),
    default=None,
)
@click.option(
    "-o",
    "--output",
    "output_dir",
    type=click.Path(exists=True, path_type=Path),
    default=None,
)
@click.option("-d", "--cldf", "cldf", default=False, is_flag=True)
@click.option("-d", "--rich", "rich", default=False, is_flag=True)
def wordlist(filename, config_file, cldf, output_dir, rich):
    if not output_dir:
        output_dir = Path(filename.parents[0])
    if rich:
        cldf_mode = "rich"
    else:
        cldf_mode = "wordlist"
    lift2csv_convert(
        filename,
        conf=_load_config(config_file),
        cldf=cldf,
        output_dir=output_dir,
        cldf_mode=cldf_mode,
    )


@main.command()
@click.argument("filename", type=click.Path(exists=True, path_type=Path))
@click.option(
    "-c",
    "--conf",
    "config_file",
    type=click.Path(exists=True, path_type=Path),
    default=None,
)
@click.option(
    "-o",
    "--output",
    "output_dir",
    type=click.Path(exists=True, path_type=Path),
    default=".",
)
@click.option(
    "-l",
    "--lexicon",
    "lexicon_file",
    type=click.Path(exists=True, path_type=Path),
    default=None,
)
@click.option(
    "-a",
    "--audio",
    "audio_folder",
    type=click.Path(exists=True, path_type=Path),
    default=None,
)
@click.option("-d", "--cldf", "cldf", default=False, is_flag=True)
def corpus(filename, config_file, lexicon_file, audio_folder, cldf, output_dir):
    conf = _load_config(config_file)
    if not output_dir:
        output_dir = Path(".")
    flex2csv_convert(
        filename,
        conf=conf,
        lexicon_file=lexicon_file,
        cldf=cldf,
        output_dir=output_dir,
        audio_folder=audio_folder,
    )


if __name__ == "__main__":
    sys.exit(main())  # pragma: no cover

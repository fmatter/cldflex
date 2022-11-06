"""Console script for cldflex."""
import sys
from pathlib import Path
import click
from cldflex.flex2csv import convert as flex2csv_convert
from cldflex.lift2csv import convert as lift2csv_convert


@click.group()
def main():
    pass  # pragma: no cover


@main.command()
@click.argument("filename")
@click.option("-c", "--conf", "config_file", default=None)
@click.option("-o", "--output", "output_dir", default=Path("."))
@click.option("-d", "--cldf", "cldf", default=False, is_flag=True)
def lift2csv(filename, config_file, cldf, output_dir):
    lift2csv_convert(
        lift_file=filename, config_file=config_file, cldf=cldf, output_dir=output_dir
    )


@main.command()
@click.argument("filename")
@click.option("-c", "--conf", "config_file", default=None)
@click.option("-o", "--output", "output_dir", default=Path("."))
@click.option("-l", "--lexicon", "lexicon_file", default=None)
@click.option("-d", "--cldf", "cldf", default=False, is_flag=True)
def flex2csv(filename, config_file, lexicon_file, cldf, output_dir):
    if not config_file and Path("config.yaml").is_file():
        config_file = "cldflex.yaml"
    flex2csv_convert(
        filename,
        config_file=config_file,
        lexicon_file=lexicon_file,
        cldf=cldf,
        output_dir=output_dir,
    )


if __name__ == "__main__":
    sys.exit(main())  # pragma: no cover

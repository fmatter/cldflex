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
    default=Path("."),
)
@click.option("-d", "--cldf", "cldf", default=False, is_flag=True)
def lift2csv(filename, config_file, cldf, output_dir):
    lift2csv_convert(
        filename, config_file=config_file, cldf=cldf, output_dir=output_dir
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
    default=Path("."),
)
@click.option(
    "-l",
    "--lexicon",
    "lexicon_file",
    type=click.Path(exists=True, path_type=Path),
    default=None,
)
@click.option("-d", "--cldf", "cldf", default=False, is_flag=True)
def flex2csv(filename, config_file, lexicon_file, cldf, output_dir):
    if not config_file:
        if Path("cldflex.yaml").is_file():
            config_file = Path("cldflex.yaml")
        else:
            config_file = None

    flex2csv_convert(
        filename,
        config_file=config_file,
        lexicon_file=lexicon_file,
        cldf=cldf,
        output_dir=output_dir,
    )


if __name__ == "__main__":
    sys.exit(main())  # pragma: no cover

"""Console script for cldflex."""
import sys
import click
import cldflex
from cldflex.flex2csv import convert as flex2csv_convert
from cldflex.lift2csv import convert as lift2csv_convert
from pathlib import Path


@click.group()
def main():
    pass  # pragma: no cover


@main.command()
def source2flex():
    cldflex.source2flex.convert(filename=sys.argv[1], mapping_file=sys.argv[2])


@main.command()
@click.argument("filename")
@click.option("-i", "--id-map", "id_map", default=None)
def lift2csv(filename, id_map):
    lift2csv_convert(lift_file=filename, id_map=id_map)


@main.command()
def flexicon2cldf():
    cldflex.flexicon2cldf.convert(filename=sys.argv[1], language_id=sys.argv[2])


@main.command()
@click.argument("filename")
@click.option("-c", "--conf", "config_file", default=None)
@click.option("-l", "--lexicon", "lexicon_file", default=None)
def flex2csv(filename, config_file, lexicon_file):
    if not config_file and Path("flex2csv.conf").is_file():
        config_file = "flex2csv.conf"
    flex2csv_convert(filename, config_file=config_file, lexicon_file=lexicon_file)


@main.command()
def bare2flex():
    cldflex.elicit2flex.convert(filename=sys.argv[1], language_id=sys.argv[2])


if __name__ == "__main__":
    sys.exit(main())  # pragma: no cover

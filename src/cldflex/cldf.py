import importlib
import logging
import sys
from pathlib import Path

import cldf_ldd
import pandas as pd
from cldfbench import CLDFSpec
from cldfbench.cldf import CLDFWriter
from cldfbench.metadata import Metadata
from humidifier import humidify
from pycldf.util import metadata2markdown
from writio import dump

from cldflex import SEPARATOR
from cldflex.helpers import listify

version = importlib.metadata.version("cldflex")


log = logging.getLogger(__name__)


def add_example_slices(sentence_slices, writer):
    writer.cldf.add_component(
        {
            "url": "ExampleSlices",
            "tableSchema": {
                "columns": [
                    {
                        "name": "ID",
                        "required": False,
                        "propertyUrl": "http://cldf.clld.org/v1.0/terms.rdf#id",
                        "datatype": {"base": "string", "format": "[a-zA-Z0-9_\\-]+"},
                    },
                    {
                        "name": "Form_ID",
                        "required": True,
                        "dc:extent": "singlevalued",
                        "datatype": "string",
                    },
                    {
                        "name": "Example_ID",
                        "required": True,
                        "dc:extent": "singlevalued",
                        "datatype": "string",
                    },
                    {
                        "name": "Index",
                        "required": True,
                        "dc:description": "Specifies the position of a form in a sentence.",
                        "datatype": {"base": "string", "format": "\\d+(:\\d+)?"},
                    },
                    {
                        "name": "Parameter_ID",
                        "required": False,
                        "propertyUrl": "http://cldf.clld.org/v1.0/terms.rdf#parameterReference",
                        "dc:description": "A reference to the meaning denoted by the form",
                        "datatype": "string",
                    },
                ]
            },
        }
    )
    writer.cldf.add_foreign_key("ExampleSlices", "Form_ID", "FormTable", "ID")
    writer.cldf.add_foreign_key("ExampleSlices", "Parameter_ID", "ParameterTable", "ID")
    writer.cldf.add_foreign_key("ExampleSlices", "Example_ID", "ExampleTable", "ID")

    for ex_slice in sentence_slices.to_dict("records"):
        writer.objects["ExampleSlices"].append(ex_slice)


def modify_params(df, mode="multi", sep=SEPARATOR, param_dict={}):
    if "Parameter_ID" in df.columns:
        with pd.option_context("mode.chained_assignment", None):
            df = listify(df, "Parameter_ID", sep)
            if mode == "single":
                df["Parameter_ID"] = df["Parameter_ID"].apply(lambda x: x[0])
            elif mode == "none":
                df["Parameter_ID"] = df["Parameter_ID"].apply(
                    lambda x: ", ".join(
                        [param_dict.get(y, "unknown meaning") for y in x]
                    )
                )
    return df


def add_metadata(writer, metadata):
    md = Metadata(**metadata)
    writer.cldf.properties.setdefault("rdf:ID", md.id)
    writer.cldf.add_provenance(
        wasGeneratedBy=[
            {
                "dc:title": "cldflex",
                "dc:description": version,
                "dc:url": "https://pypi.org/project/cldflex",
            }
        ]
    )
    for k, v in md.common_props().items():
        if k == "dc:license":
            v = v.replace(" ", "-")
        writer.cldf.properties.setdefault(k, v)
    if "dc:license" not in writer.cldf.properties:
        log.warning("You have not specified a license in your CLDF metadata.")


def add_language(writer, cwd, glottocode, iso):  # pragma: no cover
    if (Path(cwd) / "languages.csv").is_file():
        log.info(f"Using {(Path(cwd) / 'languages.csv').resolve()}")
        lg_df = pd.read_csv(Path(cwd) / "languages.csv", keep_default_na=False)
        writer.cldf.add_component("LanguageTable")
        for lg in lg_df.to_dict("records"):
            writer.objects["LanguageTable"].append(lg)
        return lg["ID"]
    log.info(
        f"No languages.csv file found, fetching language info for [{glottocode or iso}] from glottolog..."
    )
    err_msg = "Either add a languages.csv file to the working directory or run:\n\tpip install cldfbench[glottolog]"
    try:
        from cldfbench.catalogs import (  # pylint: disable=import-outside-toplevel
            Glottolog,
            pyglottolog,
        )
    except ImportError:
        log.error(err_msg)
    if isinstance(pyglottolog, str):
        log.error(err_msg)
        sys.exit()
    glottolog = pyglottolog.Glottolog(Glottolog.from_config().repo.working_dir)
    if glottocode:
        languoid = glottolog.languoid(glottocode)
    elif iso:
        languoid = glottolog.languoid(iso)
    else:
        log.error("Define either glottocode or lang_id in your conf.")
        sys.exit()
    writer.cldf.add_component("LanguageTable")
    writer.objects["LanguageTable"].append(
        {
            "ID": languoid.id,
            "Latitude": languoid.latitude,
            "Longitude": languoid.longitude,
            "Name": languoid.name,
        }
    )
    return languoid.id


def write_readme(ds):
    readme = metadata2markdown(ds, ds.directory)
    dump(
        f"**This dataset was automatically created by [cldflex](https://pypi.org/project/cldflex).**\n\n{readme}",
        ds.directory / "README.md",
    )


def create_corpus_dataset(
    tables,
    glottocode=None,
    iso=None,
    metadata=None,
    output_dir=Path("."),
    cwd=".",
    sep=SEPARATOR,
    parameters="multi",
):
    cldf_dict = {"examples": "ExampleTable", "media": "MediaTable"}
    if parameters:
        cldf_dict["senses"] = "ParameterTable"
        if "senses" not in tables:
            params = []
            for table in tables.values():
                if "Parameter_ID" in table:
                    params.extend(list(table["Parameter_ID"]))
            param_dict = {
                x: humidify(x, key="meanings", unique=True) for x in set(params)
            }
            tables["senses"] = pd.DataFrame.from_dict(
                [{"ID": v, "Name": k} for k, v in param_dict.items()]
            )
            for table in tables.values():
                table = modify_params(
                    table,
                    mode=parameters,
                    param_dict=param_dict,
                )
        else:
            param_dict = dict(zip(tables["senses"]["ID"], tables["senses"]["Name"]))

    table_dict = {
        "morphs": cldf_ldd.MorphTable,
        "morphemes": cldf_ldd.MorphemeTable,
        "wordforms": cldf_ldd.WordformTable,
        "stems": cldf_ldd.StemTable,
        "lexemes": cldf_ldd.LexemeTable,
        "exampleparts": cldf_ldd.ExampleParts,
        "wordformparts": cldf_ldd.WordformParts,
        "glosses": cldf_ldd.GlossTable,
        "texts": cldf_ldd.TextTable,
    }

    spec = CLDFSpec(
        dir=output_dir / "cldf", module="Generic", metadata_fname="metadata.json"
    )
    with CLDFWriter(spec) as writer:
        glottocode = add_language(writer, cwd, glottocode, iso)

        for name, table in {**table_dict, **cldf_dict}.items():
            if name in tables:
                if glottocode:
                    with pd.option_context("mode.chained_assignment", None):
                        tables[name]["Language_ID"] = glottocode
                writer.cldf.add_component(table)

        cldf_ldd.add_columns(writer.cldf)

        if parameters == "multi":
            for name, table in tables.items():
                table = modify_params(table)
                if name in table_dict and "Parameter_ID" in tables[name].columns:
                    writer.cldf.remove_columns(table_dict[name]["url"], "Parameter_ID")
                    writer.cldf.add_columns(
                        table_dict[name]["url"],
                        {
                            "name": "Parameter_ID",
                            "required": True,
                            "propertyUrl": "http://cldf.clld.org/v1.0/terms.rdf#parameterReference",
                            "dc:description": f"A reference to the meaning denoted by the {name[0:-1]}",
                            "datatype": "string",
                            "separator": sep,
                            "dc:extent": "multivalued",
                        },
                    )
        elif parameters == "single":  # force 1 meaning in cases of polysemy
            for table in tables.values():
                table = modify_params(table, mode="single")
        else:
            for table in tables.values():
                table = modify_params(
                    table,
                    mode="none",
                    param_dict=param_dict,
                )
        for name, table in table_dict.items():
            if name in tables:
                for rec in tables[name].to_dict("records"):
                    writer.objects[table["url"]].append(rec)

        for name, table in cldf_dict.items():
            if name in tables:
                for rec in tables[name].to_dict("records"):
                    writer.objects[table].append(rec)
    add_metadata(writer, metadata)
    cldf_ldd.add_keys(writer.cldf)
    writer.write()

    ds = writer.cldf
    if ds.validate(log=log):
        log.info(f"Validated dataset at {ds.directory.resolve()}/{ds.filename}")
        write_readme(ds)


def write_wordlist_dataset(  # noqa: MC0001
    forms,
    senses,
    glottocode=None,
    iso=None,
    metadata=None,
    output_dir=Path("."),
    cwd=".",
    sep=SEPARATOR,
    parameters="multi",
):  # pylint: disable=too-many-locals
    metadata = metadata or {}
    spec = CLDFSpec(
        dir=output_dir / "cldf", module="Wordlist", metadata_fname="metadata.json"
    )
    with CLDFWriter(spec) as writer:
        glottocode = add_language(writer, cwd, glottocode, iso)
        tablelist = [("FormTable", forms)]
        if parameters:
            tablelist.append(("ParameterTable", senses))
            writer.cldf.add_component("ParameterTable")
        if parameters == "multi":
            forms = modify_params(forms)
            writer.cldf.remove_columns("FormTable", "Parameter_ID")
            writer.cldf.add_columns(
                "FormTable",
                {
                    "name": "Parameter_ID",
                    "required": True,
                    "propertyUrl": "http://cldf.clld.org/v1.0/terms.rdf#parameterReference",
                    "dc:description": "A reference to the meaning denoted by the form",
                    "datatype": "string",
                    "separator": sep,
                },
            )
        elif parameters == "single":  # force 1 meaning in cases of polysemy
            forms = modify_params(forms, mode="single")
        for table, df in tablelist:
            for rec in df.to_dict("records"):
                writer.objects[table].append(rec)
        writer.write()
        return writer.cldf


def create_wordlist_dataset(
    forms,
    senses,
    glottocode=None,
    iso=None,
    metadata=None,
    output_dir=Path("."),
    cwd=".",
    sep=SEPARATOR,
    parameters="multi",
):
    log.info("Creating CLDF dataset")
    ds = write_wordlist_dataset(
        forms,
        senses,
        glottocode,
        iso,
        metadata,
        output_dir=output_dir,
        cwd=cwd,
        sep=sep,
        parameters=parameters,
    )
    if ds.validate(log=log, validators=cldf_ldd.validators):
        log.info(f"Validated dataset at {ds.directory.resolve()}/{ds.filename}")
        write_readme(ds)


def write_dictionary_dataset(
    entries,
    senses,
    examples,
    glottocode=None,
    iso=None,
    metadata=None,
    output_dir=".",
    cwd=".",
):
    spec = CLDFSpec(dir=output_dir / "cldf", module="Dictionary")
    with CLDFWriter(spec) as writer:
        entries["Headword"] = entries["Form"]
        entries["Part_Of_Speech"] = entries["Gramm"]
        for entry in entries.to_dict("records"):
            writer.objects["EntryTable"].append(entry)
        for sense in senses.to_dict("records"):
            writer.objects["SenseTable"].append(sense)
        if len(examples) > 0:
            writer.cldf.add_component("ExampleTable")
            for example in examples.to_dict("records"):
                writer.objects["ExampleTable"].append(example)
        if glottocode:
            add_language(writer, cwd, glottocode, iso)
        if metadata:
            add_metadata(writer, metadata)
        writer.write()
        return writer.cldf


def create_dictionary_dataset(
    entries, senses, examples, glottocode=None, metadata=None, output_dir=".", cwd="."
):
    metadata = metadata or {}
    ds = write_dictionary_dataset(
        entries,
        senses,
        examples,
        glottocode=glottocode,
        metadata=metadata,
        output_dir=output_dir,
        cwd=cwd,
    )
    if ds.validate(log=log):
        log.info(f"Validated dataset at {ds.directory.resolve()}/{ds.filename}")
        write_readme(ds)

import logging
import sys
from pathlib import Path
import pandas as pd
from cldfbench import CLDFSpec
from cldfbench.cldf import CLDFWriter
from cldfbench.metadata import Metadata
from pycldf.util import metadata2markdown
from cldflex import __version__
from cldflex.helpers import slug


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


def add_morphology_tables(tables, writer):
    try:
        from clld_morphology_plugin.cldf import FormSlices  # pylint: disable=import-outside-toplevel
        from clld_morphology_plugin.cldf import MorphsetTable  # pylint: disable=import-outside-toplevel
        from clld_morphology_plugin.cldf import MorphTable  # pylint: disable=import-outside-toplevel
    except ImportError:  # pragma: no cover
        log.error(
            "Run pip install cldflex[extras] to install the clld-morphology plugin, needed to create a dataset with morphs, morphemes and form slices."
        )
        sys.exit()
    tablemap = {
        "FormSlices": FormSlices,
        "MorphTable": MorphTable,
        "MorphsetTable": MorphsetTable,
    }
    for table, df in tables.items():
        writer.cldf.add_component(tablemap[table])
        for rec in df.to_dict("records"):
            writer.objects[table].append(rec)
    if "FormSlices" in tables:
        writer.cldf.add_foreign_key("FormSlices", "Form_ID", "FormTable", "ID")
        writer.cldf.add_foreign_key("FormSlices", "Morph_ID", "MorphTable", "ID")
        writer.cldf.add_foreign_key(
            "FormSlices", "Form_Meaning", "ParameterTable", "ID"
        )
        writer.cldf.add_foreign_key(
            "FormSlices", "Morpheme_Meaning", "ParameterTable", "ID"
        )


def create_dataset(  # noqa: MC0001
    tables, glottocode=None, metadata=None, output_dir=Path("."), cwd="."
):  # pylint: disable=too-many-locals
    log.debug("Creating dataset")
    metadata = metadata or {}
    spec = CLDFSpec(
        dir=output_dir / "cldf", module="Generic", metadata_fname="metadata.json"
    )
    with CLDFWriter(spec) as writer:

        forms = tables.get("FormTable", None)
        records = tables.get("ExampleTable", None)
        sentence_slices = tables.get("SentenceSlices", None)
        morphs = tables.get("MorphTable", None)
        texts = tables.get("TextTable", None)
        senses = tables.get("SenseTable", None)

        log.debug(tables.keys())
        if forms is not None:
            log.debug("Forms")
            writer.cldf.add_component("FormTable")
            writer.cldf.add_component("ParameterTable")  # Form meanings
            # Gather all encountered meanings and create ID slugs
            meanings = {}
            for form in forms.to_dict("records"):
                mslug = slug(form["Meaning"])
                meanings.setdefault(mslug, form["Meaning"])
                # Replace the glossed meaning with the slug and write directly to the dataset
                form["Parameter_ID"] = mslug
                writer.objects["FormTable"].append(form)
                # Write meanings
            for k, v in meanings.items():
                writer.objects["ParameterTable"].append({"ID": k, "Name": v})

        if records is not None:
            log.debug("Examples")
            writer.cldf.add_component("ExampleTable")  # Sentences
            writer.cldf.add_columns(
                "ExampleTable",
                # examples can refer to texts
                {
                    "name": "Text_ID",
                    "dc:extent": "singlevalued",
                    "dc:description": "The text to which this record belongs",
                    "datatype": "string",
                },
                # if they do, they have a number inside that text
                {
                    "name": "Part",
                    "dc:extent": "singlevalued",
                    "dc:description": "Position in the text",
                    "datatype": "integer",
                },
            )
            # The default sentence metadata expect a list, not a tab-delimited string.
            for col in ["Analyzed_Word", "Gloss"]:
                records[col] = records[col].apply(lambda x: x.split("\t"))
            for ex in records.to_dict("records"):
                writer.objects["ExampleTable"].append(ex)

        if sentence_slices is not None:
            log.debug("Slices")
            add_example_slices(sentence_slices, writer)

        if senses is not None:
            log.debug("Senses (from lexicon)")
            senses["Name"] = senses["Description"]
            for sense in senses.to_dict("records"):
                writer.objects["ParameterTable"].append(sense)

        if morphs is not None:
            log.debug("Morphs and such")
            log.debug(tables.keys())
            add_morphology_tables(
                {
                    x: y
                    for x, y in tables.items()
                    if x in ["MorphTable", "MorphsetTable", "FormSlices"]
                },
                writer,
            )
        if texts is not None:
            try:
                from clld_corpus_plugin.cldf import TextTable  # pylint: disable=import-outside-toplevel
            except ImportError:  # pragma: no cover
                log.error(
                    "Run pip install cldflex[extras] to install the clld-corpus plugin, needed to create a dataset with morphs, morphemes and form slices."
                )
                sys.exit()
            writer.cldf.add_component(TextTable)
            for text in texts.to_dict("records"):
                item = {}
                for k, v in text.items():
                    if "title_" in k and "Title" not in texts:
                        item.setdefault("Title", [])
                        item["Title"].append(v)
                    item[k] = v
                item["Title"] = " / ".join(item["Title"])
                writer.objects["TextTable"].append(item)

        if (Path(cwd) / "languages.csv").is_file():
            log.info(f"Using {(Path(cwd) / 'languages.csv').resolve()}")
            lg_df = pd.read_csv(Path(cwd) / "languages.csv", keep_default_na=False)
            writer.cldf.add_component("LanguageTable")
            for lg in lg_df.to_dict("records"):
                writer.objects["LanguageTable"].append(lg)
        else:  # pragma: no cover
            log.info(
                f"No languages.csv file found, fetching language info for [{glottocode}] from glottolog"
            )
            err_msg = "Either add a languages.csv file to the working directory or run:\n\tpip install cldfbench[glottolog]"
            try:
                from cldfbench.catalogs import Glottolog  # pylint: disable=import-outside-toplevel
                from cldfbench.catalogs import pyglottolog  # pylint: disable=import-outside-toplevel
            except ImportError:
                log.error(err_msg)
            if isinstance(pyglottolog, str):
                log.error(err_msg)

            glottolog = pyglottolog.Glottolog(Glottolog.from_config().repo.working_dir)
            languoid = glottolog.languoid(glottocode)
            writer.cldf.add_component("LanguageTable")
            writer.objects["LanguageTable"].append(
                {
                    "ID": languoid.id,
                    "Latitude": languoid.latitude,
                    "Longitude": languoid.longitude,
                    "Name": languoid.name,
                }
            )
        md = Metadata(**metadata)
        log.debug(md)
        writer.cldf.properties.setdefault("rdf:ID", md.id)
        writer.cldf.add_provenance(
            wasGeneratedBy=[
                {
                    "dc:title": "cldflex",
                    "dc:description": __version__,
                    "dc:url": "https://pypi.org/project/cldflex",
                }
            ]
        )
        for k, v in md.common_props().items():
            writer.cldf.properties.setdefault(k, v)

        writer.write()
        return writer.cldf


def create_cldf(tables, glottocode=None, metadata=None, output_dir=Path("."), cwd="."):
    log.info("Creating CLDF dataset")
    ds = create_dataset(tables, glottocode, metadata, output_dir=output_dir, cwd=cwd)
    log.debug("Validating")
    ds.validate(log=log)
    log.debug("Creating readme")
    readme = metadata2markdown(ds, ds.directory)
    with open(ds.directory / "README.md", "w", encoding="utf-8") as f:
        f.write(
            "**This dataset was automatically created by [cldflex](https://pypi.org/project/cldflex).**\n\n"
            + readme
        )
    log.info(f"Created CLDF dataset at {ds.directory.resolve()}/{ds.filename}")


def create_dictionary_dataset(morphemes, senses, metadata=None, output_dir="."):
    log.debug("Creating dataset")
    metadata = metadata or {}
    spec = CLDFSpec(
        dir=output_dir / "cldf", module="Generic", metadata_fname="metadata.json"
    )
    with CLDFWriter(spec) as writer:
        writer.cldf.add_component("EntryTable")
        writer.cldf.add_component("SenseTable")
        morphemes["Headword"] = morphemes["Name"]
        morphemes["Part_Of_Speech"] = morphemes["Name"]
        for morpheme in morphemes.to_dict("records"):
            writer.objects["EntryTable"].append(morpheme)
        for sense in senses.to_dict("records"):
            writer.objects["SenseTable"].append(sense)

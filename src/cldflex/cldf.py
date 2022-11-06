import logging
import sys
from pathlib import Path
import pandas as pd
from cldfbench import CLDFSpec
from cldfbench.cldf import CLDFWriter
from cldfbench.metadata import Metadata
from pycldf.util import metadata2markdown
from slugify import slugify
from cldflex import __version__


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
    writer.cldf.add_component(FormSlices)
    writer.cldf.add_component(MorphTable)
    writer.cldf.add_component(MorphsetTable)
    for table, df in tables.items():
        log.debug(table)
        for rec in df.to_dict("records"):
            writer.objects[table].append(rec)


def create_dataset(
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
        log.debug(tables.keys())
        if forms is not None:
            log.debug("Forms")
            writer.cldf.add_component("FormTable")
            writer.cldf.add_component("ParameterTable")  # Form meanings
            # Gather all encountered meanings and create ID slugs
            meanings = {}
            for form in forms.to_dict("records"):
                mslug = slugify(form["Meaning"])
                meanings.setdefault(mslug, form["Meaning"])
                # Replace the glossed meaning with the slug and write directly to the dataset
                form["Parameter_ID"] = mslug
                form["Form"] = (
                    form["Form"].replace("-", "").replace("=", "").replace("Ø", "")
                )  # Assuming that we want unsegmented forms in the FormTable
                writer.objects["FormTable"].append(form)
                # Write meanings
            for k, v in meanings.items():
                writer.objects["ParameterTable"].append({"ID": k, "Name": v})

        if records is not None:
            log.debug("Examples")
            writer.cldf.add_component("ExampleTable")  # Sentences
            # The default sentence metadata expect a list, not a tab-delimited string.
            for col in ["Analyzed_Word", "Gloss"]:
                records[col] = records[col].apply(lambda x: x.split("\t"))
            for ex in records.to_dict("records"):
                writer.objects["ExampleTable"].append(ex)

        if sentence_slices is not None:
            log.debug("Slices")
            add_example_slices(sentence_slices, writer)

        if morphs is not None:
            log.debug("Morphs and such")
            morphs.rename(columns={"Form": "Name"}, inplace=True)
            log.debug(tables.keys())
            add_morphology_tables(
                {
                    x: y
                    for x, y in tables.items()
                    if x in ["MorphTable", "MorphsetTable", "FormSlices"]
                },
                writer,
            )

        if (Path(cwd) / "languages.csv").is_file():
            log.info("Using languages.csv for CLDF dataset creation")
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
        log.warning(md)
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
    ds = create_dataset(tables, glottocode, metadata, output_dir=output_dir, cwd=cwd)
    log.debug("Validating")
    ds.validate(log=log)
    log.debug("Creating readme")
    readme = metadata2markdown(ds, ds.directory)
    with open(ds.directory / "README.md", "w", encoding="utf-8") as f:
        f.write(readme)
    log.info(f"Created cldf dataset at {ds.directory.resolve()}/{ds.filename}")


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

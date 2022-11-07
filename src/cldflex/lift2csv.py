import logging
from pathlib import Path
import pandas as pd
import yaml
from bs4 import BeautifulSoup
from slugify import slugify
from cldflex.cldf import create_dictionary_dataset


log = logging.getLogger(__name__)


def gather_variants(entry, variant_dict):
    relations = entry.find_all("relation")
    if relations:
        for relation in relations:
            if relation.select("trait[name='variant-type']") and relation["ref"] != "":
                main_entry_id = relation["ref"].split("_")[-1]
                variant_dict.setdefault(main_entry_id, [])
                variant_dict[main_entry_id].append(
                    {
                        "ID": slugify(entry["id"]),
                        "Form": entry.find("form").text,
                        "Type": entry.select("trait[name='morph-type']")[0]["value"],
                    }
                )


def get_morph_type(entry):
    return entry.select("trait[name='morph-type']", recursive=False)[0]["value"]


def extract_glosses(sense, fields):
    glosses = []
    for gloss in sense.find_all("gloss"):
        key = "gloss_" + gloss["lang"]
        fields.setdefault(key, [])
        fields[key].append(gloss.text)
        glosses.append(gloss.text)
    return glosses


def extract_examples(sense, dictionary_examples, entry_id):
    for ex_count, example in enumerate(sense.find_all("example")):
        example_dict = {"ID": f"{entry_id}-{ex_count}"}
        for child in example.find_all(recursive=False):
            if child.name == "form":
                example_dict["Form"] = child.text
            else:
                child_form = child.find("form")
                example_dict[
                    f"{child.name}-{slugify(child['type'])}-{child_form['lang']}"
                ] = child_form.text
        for attr in example.attrs:
            example_dict[attr] = example[attr]
        dictionary_examples.append(example_dict)


def extract_forms(
    entry_part, entry_id, morph_type, morphs, fields, form_count
):  # pylint: disable=too-many-arguments
    for form in entry_part.find_all("form"):
        f_dict = {
            "ID": f"{entry_id}-{form_count}",
            "Form": form.text,
            "Type": morph_type,
            "Morpheme_ID": entry_id,
        }
        f_dict.update(**fields)
        morphs.append(f_dict)
        form_count += 1
    return form_count


def parse_entry(entry, senses, dictionary_examples, variant_dict=None):
    entry_id = entry["guid"]
    variant_dict = variant_dict or {}
    morpheme_type = get_morph_type(entry)
    poses = []
    morphs = []
    fields = {"Parameter_ID": []}

    for sense in entry.find_all("sense", recursive=False):
        # POS are stored in senses
        for gramm in sense.find_all("grammatical-info"):
            poses.append(gramm["value"])
        # and glosses
        glosses = extract_glosses(sense, fields)
        fields["Parameter_ID"].append(sense.attrs["id"])
        senses.append(
            {
                "ID": sense.attrs["id"],
                "Description": ", ".join(glosses),
                "Entry_ID": entry_id,
            }
        )
        # examples are stored in senses
        extract_examples(sense, dictionary_examples, entry_id)

    # go through form(s?)
    form_count = 0
    form_count = extract_forms(
        entry.find("lexical-unit"), entry_id, morpheme_type, morphs, fields, form_count
    )

    # go through allomorphs / variants
    for variant in entry.find_all("variant"):
        form_count = extract_forms(
            variant, entry_id, get_morph_type(variant), morphs, fields, form_count
        )

    # gather variants stored in other dictionary entries
    for variant in variant_dict.get(entry_id, []):
        variant["Morpheme_ID"] = entry_id
        variant.update(**fields)
        morphs.append(variant)

    morpheme_dict = {
        "ID": entry_id,
        "Gramm": poses,
        "Type": morpheme_type,
        "Form": [x["Form"] for x in morphs],
        "Name": morphs[0]["Form"],
    }
    morpheme_dict.update(**fields)
    return morpheme_dict, morphs


def convert(
    lift_file="", output_dir=".", sep="; ", config_file=None, cldf=False
):  # pylint: disable=too-many-locals
    if not config_file:
        log.warning("No configuration file or dict provided.")
        conf = {}
    else:
        with open(config_file, encoding="utf-8") as f:
            conf = yaml.safe_load(f)
    obj_lg = conf.get("obj_lg", None)
    gloss_lg = conf.get("gloss_lg", None)
    lg_id = conf.get("Language_ID", None)
    output_dir = Path(output_dir)
    with open(lift_file, "r", encoding="utf-8") as f:
        lexicon = BeautifulSoup(f.read(), features="xml")
    morphemes = []
    morphs = []
    entries = []
    senses = []
    variant_dict = {}
    dictionary_examples = []
    for entry in lexicon.find_all("entry"):
        if not gather_variants(entry, variant_dict):
            entries.append(entry)
    for entry in entries:
        if not gloss_lg:
            gloss_lg = entry.find("gloss")["lang"]
            log.info(f"Using [{gloss_lg}] as the main meta language ('Meaning' column)")
        if not obj_lg:
            obj_lg = entry.find("form")["lang"]
            log.info(f"Assuming [{obj_lg}] to be the object language")
        morpheme, allomorphs = parse_entry(
            entry, senses, dictionary_examples, variant_dict=variant_dict
        )
        morphemes.append(morpheme)
        morphs.extend(allomorphs)
    morphemes = pd.DataFrame.from_dict(morphemes)
    morphs = pd.DataFrame.from_dict(morphs)
    for df in [morphs, morphemes]:
        df.rename(columns={f"gloss_{gloss_lg}": "Meaning"}, inplace=True)
        if lg_id:
            df["Language_ID"] = lg_id
        else:
            df["Language_ID"] = obj_lg
        df.fillna("", inplace=True)
        for col in df.columns:
            if isinstance(df[col].iloc[0], list):
                df[col] = df[col].apply(sep.join)

    morphs.to_csv(output_dir / "morphs.csv", index=False)
    morphemes.to_csv(output_dir / "morphemes.csv", index=False)
    senses = pd.DataFrame.from_dict(senses)
    senses.to_csv(output_dir / "senses.csv", index=False)
    if dictionary_examples:
        dictionary_examples = pd.DataFrame.from_dict(dictionary_examples)
        dictionary_examples.to_csv(output_dir / "dictionary_examples.csv", index=False)

    if cldf:
        create_dictionary_dataset(morphemes, senses, output_dir=output_dir)

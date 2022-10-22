import logging
from pathlib import Path
from xml.etree.ElementTree import fromstring
import pandas as pd
import yaml
from bs4 import BeautifulSoup
from slugify import slugify
from xmljson import badgerfish as bf
from cldflex.helpers import listify


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
    return None


def get_morph_type(entry):
    return entry.select("trait[name='morph-type']", recursive=False)[0]["value"]


def parse_entry(entry, dictionary_examples, variant_dict=None, sep="; "):
    entry_id = entry["guid"]
    variant_dict = variant_dict or {}
    forms = []
    morpheme_type = get_morph_type(entry)
    poses = []
    morphs = []
    fields = {}

    for sense in entry.find_all("sense", recursive=False):
        # POS
        for gramm in sense.find_all("grammatical-info"):
            poses.append(gramm["value"])
            # glosses for this sense
        for gloss in sense.find_all("gloss"):
            key = "gloss_" + gloss["lang"]
            fields.setdefault(key, [])
            fields[key].append(gloss.text)
            # examples are stored in senses
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

    # go through form(s?)
    form_count = 0
    for form in entry.find("lexical-unit").find_all("form"):
        f_dict = {
            "ID": f"{entry_id}-{form_count}",
            "Form": form.text,
            "Type": morpheme_type,
            "Morpheme_ID": entry_id,
        }
        f_dict.update(**fields)
        morphs.append(f_dict)
        forms.append(form.text)
        form_count += 1

    # go through allomorphs / variants
    for variant in entry.find_all("variant"):
        morph_type = get_morph_type(variant)
        for form in variant.find_all("form"):
            f_dict = {
                "ID": f"{entry_id}-{form_count}",
                "Form": form.text,
                "Type": morph_type,
                "Morpheme_ID": entry_id,
            }
            f_dict.update(**fields)
            morphs.append(f_dict)
            forms.append(form.text)
            form_count += 1

    # gather variants stored in other dictionary entries
    for variant in variant_dict.get(entry_id, []):
        variant["Morpheme_ID"] = entry_id
        variant.update(**fields)
        morphs.append(variant)

    morpheme_dict = {
        "ID": entry_id,
        "Gramm": poses,
        "Type": morpheme_type,
        "Form": forms,
        "Name": forms[0],
    }
    morpheme_dict.update(**fields)
    return morpheme_dict, morphs


def convert(
    lift_file="",
    id_map=None,
    gather_examples=True,
    output_dir=None,
    gloss_lg=None,
    obj_lg=None,
    sep="; ",
):
    lift_file = Path(lift_file)
    output_dir = output_dir or lift_file.resolve().parents[0]
    output_dir = Path(output_dir)
    with open(lift_file, "r", encoding="utf-8") as f:
        content = f.read()
    lexicon = BeautifulSoup(content, features="xml")
    morphemes = []
    morphs = []
    entries = []
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
            entry, dictionary_examples, variant_dict=variant_dict, sep=sep
        )
        morphemes.append(morpheme)
        morphs.extend(allomorphs)
    morphemes = pd.DataFrame.from_dict(morphemes)
    morphs = pd.DataFrame.from_dict(morphs)
    for df in [morphs, morphemes]:
        df.rename(columns={f"gloss_{gloss_lg}": "Meaning"}, inplace=True)
        df["Language_ID"] = obj_lg
        df.fillna("", inplace=True)
        for col in df.columns:
            if isinstance(df[col].iloc[0], list):
                df[col] = df[col].apply(lambda x: sep.join(x))

    morphs.to_csv(output_dir / "morphs.csv", index=False)
    morphemes.to_csv(output_dir / "morphemes.csv", index=False)
    if dictionary_examples:
        dictionary_examples = pd.DataFrame.from_dict(dictionary_examples)
        dictionary_examples.to_csv(output_dir / "dictionary_examples.csv", index=False)

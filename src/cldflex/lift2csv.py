from xml.etree.ElementTree import fromstring
from xmljson import badgerfish as bf
import sys
import os
import re
import pandas as pd
import unicodedata
from clldutils.loglib import Logging, get_colorlog
import sys
import logging
from cldflex.helpers import listify
import yaml
from pathlib import Path

log = get_colorlog(__name__, sys.stdout, level=logging.DEBUG)


def get_variant(morphemes, main_id, forms, id):
    out = []
    for morpheme in morphemes:
        if morpheme["ID"] == main_id:
            morpheme["Form"].extend(forms)
        out.append(morpheme)
    return out


def convert(lift_file="", id_map=None, gather_examples=True, cldf_mode="all"):
    dictionary_examples = []
    lift_file = Path(lift_file)
    log.info(f"Processing lift file {lift_file}")
    dir_path = lift_file.resolve().parents[0]
    name = lift_file.stem
    f = open(lift_file, "r")
    content = f.read().replace("http://www.w3.org/1999/xhtml", "")
    morphemes = []
    morpheme_variants = {}
    for entry in bf.data(fromstring(content))["lift"]["entry"]:
        morpheme_id = entry["@guid"]
        # different traits are stored here
        trait_entries = listify(entry["trait"])
        # we are only interested in the morpheme type (root, prefix...)
        morph_type = "root"
        for trait_entry in trait_entries:
            if trait_entry["@name"] == "morph-type":
                morph_type = trait_entry["@value"]
        # some variants are stored as separate entries
        if "relation" in entry:
            for relation in listify(entry["relation"]):
                if relation["@type"] == "_component-lexeme":
                    for trait in listify(relation["trait"]):
                        if trait["@name"] == "variant-type":
                            main_id = relation["@ref"].split("_")[-1]
                            morph = {
                                "ID": morpheme_id,
                                "Form": entry["lexical-unit"]["form"]["text"]["$"],
                                "Morpheme_ID": main_id,
                                "Type": morph_type,
                            }
                            morpheme_variants.setdefault(main_id, [])
                            morpheme_variants[main_id].append(morph)
            continue
        if "sense" not in entry:  # just skip these
            continue
        sense_entries = listify(entry["sense"])
        # there are potentially glosses in multiple languages
        # the structure differs if there is only a single language
        glosses = {}
        # every sense has its own POS value; we gather them here
        poses = []
        for sense_count, sense_entry in enumerate(sense_entries):
            if "gloss" not in sense_entry and "definition" not in sense_entry:
                continue
            if "grammatical-info" in sense_entry:
                poses.append(sense_entry["grammatical-info"]["@value"])
            if "gloss" in sense_entry:
                entry_glosses = listify(sense_entry["gloss"])
                for entry_gloss in entry_glosses:
                    gloss_lg = entry_gloss["@lang"]
                    if gloss_lg not in glosses:
                        glosses[gloss_lg] = []
                    gloss = entry_gloss["text"]["$"]
                    if gloss not in glosses[gloss_lg]:
                        glosses[gloss_lg].append(str(gloss))
            elif "definition" in sense_entry:
                entry_defs = listify(sense_entry["definition"])
                for entry_def in entry_defs:
                    form = entry_def["form"]
                    gloss_lg = form["@lang"]
                    if gloss_lg not in glosses:
                        glosses[gloss_lg] = []
                    gloss = form["text"]["$"]
                    if gloss not in glosses[gloss_lg]:
                        glosses[gloss_lg].append(str(gloss))
            if gather_examples and "example" in sense_entry:
                examples = listify(sense_entry["example"])
                for ex_cnt, example in enumerate(examples):
                    if "form" not in example:
                        continue
                    translation = example.get(
                        "translation", {"form": {"text": {"$": ""}}}
                    )
                    translation = translation.get("form", {"text": {"$": ""}})
                    translation = translation.get("text", {"$": ""})
                    if "span" in example["form"]["text"]:
                        ex_text = [
                            x["$"] for x in example["form"]["text"]["span"] if "$" in x
                        ]
                        ex_text = "".join(ex_text)
                    else:
                        ex_text = example["form"]["text"]["$"]
                    if "$" in translation:
                        dictionary_examples.append(
                        {
                            "ID": f"{morpheme_id}-{sense_count}-{ex_cnt}",
                            "Primary_Text": ex_text,
                            "Translated_Text": translation["$"],
                            "Entry_ID": morpheme_id,
                        }
                    )
        # storing citation form as list, variants are added later
        forms = [entry["lexical-unit"]["form"]["text"]["$"]]
        lg_id = entry["lexical-unit"]["form"]["@lang"]
        poses = list(set(poses))
        if len(poses) > 1:
            log.warning(
                f"Entry {forms[0]} has multiple grammatical infos: {', '.join(poses)}"
            )
        variants = listify(entry.get("variant", None))
        for i, variant in enumerate(variants):
            if not variant:
                continue
            if "form" not in variant.keys():
                continue
            variant_form = variant["form"]["text"]["$"]
            variant_morph_type = variant["trait"]["@value"]
            morpheme_variants.setdefault(morpheme_id, [])
            morpheme_variants[morpheme_id].append(
                {
                    "ID": f"{morpheme_id}-{i}",
                    "Form": variant_form,
                    "Morpheme_ID": morpheme_id,
                    "Type": variant_morph_type,
                }
            )
        morphemes.append(
            {
                "ID": morpheme_id,
                "Form": forms,
                "Name": forms[0],
                "Language_ID": lg_id,
                "Gramm": poses,
                "Type": morph_type,
            }
        )
        for gloss_lg, lg_glosses in glosses.items():
            morphemes[-1]["Meaning"] = lg_glosses

    morphs = []
    for morpheme in morphemes:
        main_morph = morpheme.copy()
        main_morph["Morpheme_ID"] = main_morph["ID"]
        main_morph["Form"] = main_morph["Form"][0]
        del main_morph["Name"]
        del main_morph["Gramm"]
        morphs.append(main_morph)
        for variant in morpheme_variants.get(morpheme["ID"], []):
            morpheme["Form"].append(variant["Form"])
            variant["Meaning"] = morpheme["Meaning"]
            variant["Language_ID"] = morpheme["Language_ID"]
            morphs.append(variant)

    # create pandas DF
    morphemes = pd.DataFrame.from_dict(morphemes)
    morphemes = morphemes.fillna("")

    # create pandas DF
    morphs = pd.DataFrame.from_dict(morphs)
    morphs = morphs.fillna("")

    # convert list columns into "; " separated text
    for df in [morphemes, morphs]:
        for col in df.columns:
            if type(df[col][0]) == list:
                df[col] = df[col].apply(lambda x: "; ".join(x))

    if id_map is not None:
        with open(id_map) as file:
            id_map = yaml.load(file, Loader=yaml.SafeLoader)
        morphemes["ID"].replace(id_map, inplace=True)
        morphs["ID"].replace(id_map, inplace=True)

    log.info("\n" + morphemes.head().to_string())
    log.info("\n" + morphs.head().to_string())
    morphemes.to_csv(dir_path / "morphemes.csv", index=False)
    morphs.to_csv(dir_path / "morphs.csv", index=False)
    if gather_examples and len(dictionary_examples) > 0:
        dictionary_examples = pd.DataFrame.from_dict(dictionary_examples)
        dictionary_examples.to_csv(dir_path / f"{name}_examples.csv", index=False)

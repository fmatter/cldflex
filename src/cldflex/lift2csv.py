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
            if "ijmoka" in forms:
                print(main_id, forms, morpheme)
            morpheme["Form"].extend(forms)
        out.append(morpheme)
    return out


def convert(lift_file="", csv_file=None, id_map=None, gather_examples=True):
    gathered_examples = []
    lift_file = Path(lift_file)
    log.info(f"Processing lift file {lift_file}")
    dir_path = lift_file.resolve().parents[0]
    name = lift_file.stem
    if not csv_file:
        csv_file = dir_path / f"{name}_from_lift.csv"
    f = open(lift_file, "r")
    content = f.read().replace("http://www.w3.org/1999/xhtml", "")
    morphemes = []
    complex_forms = []
    for entry in bf.data(fromstring(content))["lift"]["entry"]:
        morph_id = entry["@guid"]
        # skip entries referring to other entries, for now
        if "relation" in entry.keys():
            done = False
            relations = listify(entry["relation"])
            for relation in relations:
                if relation["@type"] not in ["Compare", "_component-lexeme"]:
                    done = True
                    continue
                if morph_id == "9d3c48bb-91c3-4b21-af00-38066f2770c8":
                    print(entry)
                if relation["@type"] == "_component-lexeme":
                    for trait in listify(relation["trait"]):
                        if morph_id == "007cc9cd-b24d-419e-8c04-df64cff4737d":
                            print(trait)
                        if trait["@name"] == "variant-type":
                            main_id = relation["@ref"].split("_")[-1]
                            forms = [entry["lexical-unit"]["form"]["text"]["$"]]
                            morphemes = get_variant(morphemes, main_id, forms, morph_id)
                    done = True
            if done:
                continue
        # different traits are stored here
        trait_entries = listify(entry["trait"])
        # we are interested in the morpheme type (root, prefix...)
        morph_type = ""
        for trait_entry in trait_entries:
            if trait_entry["@name"] == "morph-type":
                morph_type = trait_entry["@value"]
        # storing citation form as list, variants are added later
        forms = [entry["lexical-unit"]["form"]["text"]["$"]]
        lg_id = entry["lexical-unit"]["form"]["@lang"]
        if "sense" not in entry:  # just skip these
            continue
        sense_entries = listify(entry["sense"])
        # there are potentially glosses in multiple languages
        # the structure differs if there is only a single language...
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
                    translation = example.get("translation", {"form": {"text": {"$": ""}}})
                    translation = translation.get("form", {"text": {"$": ""}})
                    translation = translation.get("text", {"$": ""})
                    gathered_examples.append({
                        "ID": f"{morph_id}-{sense_count}-{ex_cnt}",
                        "Primary_Text": example["form"]["text"]["$"],
                        "Translated_Text": translation["$"],
                        "Entry_ID": morph_id
                    })
        poses = list(set(poses))
        if len(poses) > 1:
            log.warning(
                f"Entry {forms[0]} has multiple grammatical infos: {', '.join(poses)}"
            )
        if "variant" in entry.keys():
            variants = listify(entry["variant"])
            for variant in variants:
                if "form" not in variant.keys():
                    continue
                variant_form = variant["form"]["text"]["$"]
                variant_morph_type = variant["trait"]["@value"]
                forms.append(variant_form)
        morphemes.append(
            {"ID": morph_id, "Form": forms, "Language_ID": lg_id, "Gramm": poses}
        )
        for gloss_lg, lg_glosses in glosses.items():
            morphemes[-1]["Gloss_" + gloss_lg] = lg_glosses

    # create pandas DF
    morphemes = pd.DataFrame.from_dict(morphemes)
    morphemes = morphemes.fillna("")

    # convert list columns into "; " separated text
    for col in morphemes.columns:
        # if col == "Gloss_en":
        # for r in morphemes.to_dict(orient="records"):
        # print(r[col])
        if type(morphemes[col][0]) == list:
            morphemes[col] = morphemes[col].apply(lambda x: "; ".join(x))

    if id_map is not None:
        with open(id_map) as file:
            id_map = yaml.load(file, Loader=yaml.SafeLoader)
        morphemes["ID"].replace(id_map, inplace=True)

    log.info("\n" + morphemes.head().to_string())
    morphemes.to_csv(csv_file, index=False)

    if gather_examples:
        gathered_examples = pd.DataFrame.from_dict(gathered_examples)
        gathered_examples.to_csv(dir_path / f"{name}-examples.csv", index=False)
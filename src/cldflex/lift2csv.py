import logging
from pathlib import Path
from xml.etree.ElementTree import fromstring
import pandas as pd
import yaml
from xmljson import badgerfish as bf
from cldflex.helpers import listify


log = logging.getLogger(__name__)


def get_variant(morphemes, main_id, forms):
    out = []
    for morpheme in morphemes:
        if morpheme["ID"] == main_id:
            morpheme["Form"].extend(forms)
        out.append(morpheme)
    return out


def convert(lift_file="", id_map=None, gather_examples=True, output_dir=None):
    lift_file = Path(lift_file)
    output_dir = output_dir or lift_file.resolve().parents[0]
    output_dir = Path(output_dir)
    dictionary_examples = []
    lift_file = Path(lift_file)
    log.info(f"Processing lift file {lift_file}")
    name = lift_file.stem
    with open(lift_file, "r", encoding="utf-8") as f:
        content = f.read().replace("http://www.w3.org/1999/xhtml", "")
    morphemes = []
    morpheme_variants = {}
    for entry in bf.data(fromstring(content))["lift"]["entry"]:
        morpheme_id = entry["@guid"]
        # log.debug(morpheme_id)
        # different traits are stored here
        trait_entries = listify(entry["trait"])
        # we are only interested in the morpheme type (root, prefix...)
        morph_type = "root"
        for trait_entry in trait_entries:
            if trait_entry["@name"] == "morph-type":
                morph_type = trait_entry["@value"]
        # some variants are stored as separate entries
        variant_entry = False
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
                            variant_entry = True
        if variant_entry:
            continue
        if "sense" not in entry:  # just skip entries without a sense (meaning)
            log.info(f"Skipping entry [{morpheme_id}] -- no senses.")
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
        if "Meaning" not in morphemes[-1]:
            morphemes[-1]["Meaning"] = ""
        if "field" in entry:
            for field_entry in listify(entry["field"]):
                morphemes[-1][field_entry["@type"]] = field_entry["form"]["text"]["$"]

    morphs = []
    for morpheme in morphemes:
        main_morph = morpheme.copy()
        main_morph["Morpheme_ID"] = main_morph["ID"]
        main_morph["Form"] = main_morph["Form"][0]
        del main_morph["Name"]
        del main_morph["Gramm"]
        morphs.append(main_morph)
        # log.debug(morpheme)
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
            if isinstance(df[col][0], list):
                df[col] = df[col].apply(lambda x: "; ".join(x))

    if id_map is not None:
        with open(id_map, "r", encoding="utf-8") as file:
            id_map = yaml.load(file, Loader=yaml.SafeLoader)
        morphemes["ID"].replace(id_map, inplace=True)
        morphs["ID"].replace(id_map, inplace=True)

    log.info(f"\n{morphemes.head().to_string()}")
    log.info(f"\n{morphs.head().to_string()}")
    morphemes.to_csv(output_dir / "morphemes.csv", index=False)
    morphs.to_csv(output_dir / "morphs.csv", index=False)
    if gather_examples and len(dictionary_examples) > 0:
        dictionary_examples = pd.DataFrame.from_dict(dictionary_examples)
        dictionary_examples.to_csv(output_dir / f"{name}_examples.csv", index=False)

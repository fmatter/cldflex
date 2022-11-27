import logging
import re
import sys
from pathlib import Path
import pandas as pd
import yaml
from bs4 import BeautifulSoup
from slugify import slugify
from cldflex.cldf import create_cldf
from cldflex.cldf import create_dictionary_dataset
from cldflex.helpers import add_to_list_in_dict
from cldflex.helpers import deduplicate
from cldflex.helpers import delistify


log = logging.getLogger(__name__)


def extract_examples(sense, dictionary_examples, sense_id):
    for ex_count, example in enumerate(sense.find_all("example")):
        example_dict = {"ID": f"{sense_id}-{ex_count}", "Sense_ID": sense_id}
        for child in example.find_all(recursive=False):
            if child.name == "form":
                example_dict["Primary_Text"] = child.text
            elif child.name == "translation":
                example_dict["Translated_Text"] = child.find("form").find("text").text
            else:
                child_form = child.find("form")
                if child_form:
                    example_dict[
                        f"{child.name}-{slugify(child['type'])}-{child_form['lang']}"
                    ] = child_form.text
                else:
                    log.warning(f"Sense {sense_id} has empty examples")
        for attr in example.attrs:
            example_dict[attr] = example[attr]
        dictionary_examples.append(example_dict)


def figure_out_gloss_language(entry):
    gloss_lg = None
    if entry.find("gloss"):
        gloss_lg = entry.find("gloss")["lang"]
    elif entry.find("definition"):
        gloss_lg = entry.find("definition").find("form")["lang"]
    if gloss_lg:
        log.info(f"Using [{gloss_lg}] as the main meta language ('Meaning' column)")
    return gloss_lg


def parse_entries(entries):
    parsed = []
    morph_list = []
    senses = []
    dictionary_examples = []
    for entry in entries:
        fields = {"Gramm": [], "Parameter_ID": []}
        entry_id = entry["guid"]
        fields["ID"] = entry_id
        main_morph = {"ID": entry["guid"] + "-0", "Morpheme_ID": entry["guid"]}
        for trait in entry.find_all("trait", recursive=False):
            fields[trait["name"]] = trait["value"]
        for lexical_unit in entry.find_all("lexical-unit", recursive=False):
            for form in lexical_unit.find_all("form"):
                fields["form_" + form["lang"]] = form.text
                main_morph["form_" + form["lang"]] = form.text
        for field in entry.find_all("field", recursive=False):
            for pseudoform in field.find_all("form"):
                fields[
                    slugify(field["type"]) + "_" + pseudoform["lang"]
                ] = pseudoform.text
        for relation in entry.find_all("relation", recursive=False):
            for trait in relation.find_all("trait"):
                if "_" not in relation["ref"]:
                    continue
                add_to_list_in_dict(
                    fields,
                    f"""relation{relation["type"]}_{trait["name"]}_{slugify(trait["value"])}""",
                    relation["ref"].split("_")[1],
                )

        for sense in entry.find_all("sense", recursive=False):
            sense_id = sense["id"]  # todo human-readable option
            sense_dict = {"ID": sense_id, "Entry_ID": entry_id}
            fields["Parameter_ID"].append(sense["id"])
            for gramm in sense.find_all("grammatical-info"):
                fields["Gramm"].append(gramm["value"])
            for definition in sense.find_all("definition"):
                for pseudoform in definition.find_all("form"):
                    for x in [fields, sense_dict]:
                        add_to_list_in_dict(
                            x, "definition_" + pseudoform["lang"], pseudoform.text
                        )
            for gloss in sense.find_all("gloss"):
                key = "gloss_" + gloss["lang"]
                for x in [fields, main_morph, sense_dict]:
                    add_to_list_in_dict(x, key, gloss.text)
            for note in sense.find_all("note"):
                note_type = ("note_" + note.get("type", "")).strip("_")
                for pseudoform in note.find_all("form"):
                    add_to_list_in_dict(
                        fields, note_type + "_" + pseudoform["lang"], pseudoform.text
                    )
            for reversal in sense.find_all("reversal"):
                for form in reversal.find_all("form"):
                    add_to_list_in_dict(fields, "reversal_" + form["lang"], form.text)
            senses.append(sense_dict)
            extract_examples(sense, dictionary_examples, sense_id)

        main_morph["morph-type"] = fields.get("morph-type", "?")
        main_morph["Parameter_ID"] = fields.get("Parameter_ID", "na")
        morph_list.append(main_morph)
        for i, allomorph in enumerate(entry.find_all("variant", recursive=False)):
            form = allomorph.find("form")
            add_to_list_in_dict(fields, "variant_" + form["lang"], form.text)
            new_morph = main_morph.copy()
            new_morph["ID"] = f"""{entry["guid"]}-{i+1}"""
            new_morph["Parameter_ID"] = fields.get("Parameter_ID", "na")
            new_morph["morph-type"] = allomorph.select("trait[name='morph-type']")[0][
                "value"
            ]
            for form in allomorph.find_all("form"):
                new_morph["form_" + form["lang"]] = form.text
            morph_list.append(new_morph)
        fields["Gramm"] = deduplicate(fields["Gramm"])
        parsed.append(fields)
    return parsed, morph_list, senses, dictionary_examples


def convert(
    lift_file, output_dir=".", config_file=None, cldf=False, conf=None
):  # pylint: disable=too-many-locals
    if not lift_file.suffix == ".lift":
        log.error("Please provide a .lift file.")
        sys.exit()
    if not conf and not config_file:
        log.info("Running without configuration file or dict.")
        conf = {}
    elif not conf:
        with open(config_file, encoding="utf-8") as f:
            conf = yaml.safe_load(f)
    sep = conf.get("csv_cell_separator", "; ")
    obj_lg = conf.get("obj_lg", None)
    gloss_lg = conf.get("gloss_lg", None)
    log.info(f"Parsing {lift_file.resolve()}")
    with open(lift_file, "r", encoding="utf-8") as f:
        lexicon = BeautifulSoup(f.read(), features="xml")

    for entry in lexicon.find_all("entry"):
        if not gloss_lg:
            gloss_lg = figure_out_gloss_language(entry)
        if not obj_lg:
            obj_lg = entry.find("form")["lang"]

    obj_key = f"form_{obj_lg}"
    definition_key = f"definition_{gloss_lg}"
    gloss_key = f"gloss_{gloss_lg}"
    var_key = "variant_" + obj_lg

    var_dict = {}
    entries, morph_list, senses, dictionary_examples = parse_entries(
        lexicon.find_all("entry")
    )
    entries = pd.DataFrame.from_dict(entries)
    senses = pd.DataFrame.from_dict(senses)
    senses["Description"] = senses.apply(
        lambda x: x[definition_key]
        if not pd.isnull(x[definition_key])
        else x[gloss_key],
        axis=1,
    )
    senses["Name"] = senses.apply(
        lambda x: " / ".join(x[gloss_key])
        if not pd.isnull(x[gloss_key]).any()
        else x[definition_key],
        axis=1,
    )
    unmodified_entries = entries.copy()

    def entry_repr(entry_id):
        entry = entries[entries["ID"] == entry_id].iloc[0]
        if not isinstance(entry[gloss_key], list):
            ggg = "unknown meaning"
        elif len(entry[gloss_key]) == 0:
            ggg = "unknown meaning"
        else:
            ggg = " / ".join(entry[gloss_key])
        if isinstance(entry.get(obj_key, None), list):
            form_str = " / ".join(entry[obj_key])
        else:
            form_str = entry.get(obj_key, "MISSING FORM")
        return f"""{form_str} '{ggg}' ({','.join(entry["Gramm"])}, {entry["morph-type"]}) [{entry["ID"]}]"""

    for col in entries.columns:
        if "variant-type" not in col:
            continue
        variants = entries[~(pd.isnull(entries[col]))]
        for entry in variants.to_dict("records"):
            if len(entry[col]) > 1:
                msg = f"""The entry {entry_repr(entry["ID"])} is stored as a variant ({col}) of multiple main entries:"""
                for entry_id in entry[col]:
                    msg += "\n" + entry_repr(entry_id)
                log.warning(msg)
            for entry_id in entry[col]:
                add_to_list_in_dict(var_dict, entry_id, entry)

    check_variants = var_key in entries.columns

    entries["Name"] = entries[obj_key]
    entries[obj_key] = entries[obj_key].apply(
        lambda x: [x] if isinstance(x, str) else []
    )
    for key in [gloss_key, definition_key]:
        if key in entries:
            entries[key] = entries[key].apply(
                lambda x: [] if not isinstance(x, list) else x
            )

    def process_variant(entry, variant, new_variant_morphs, var_dict, var_count, i):
        if variant["ID"] in var_dict:
            for varvariant in var_dict[variant["ID"]]:
                log.warning(
                    f"""The variant {entry_repr(variant["ID"])} of the entry {entry_repr(entry["ID"])} has the subvariant {entry_repr(varvariant["ID"])}. Is this accurate?"""
                )
                varvariant = varvariant.copy()
                process_variant(
                    entry, varvariant, new_variant_morphs, var_dict, var_count, i
                )
                var_count += 1
        log.debug(
            f"""Adding variant {variant["ID"]} {variant[obj_key]} to entry {entry_repr(entry["ID"])}"""
        )
        if variant["Gramm"] and variant["Gramm"] != entry["Gramm"]:
            log.warning(
                f"""The entry {entry_repr(variant["ID"])} is stored as a variant of {entry_repr(entry["ID"])}. It will not retain its part of speech."""
            )
        if gloss_key in variant and not pd.isnull(variant[gloss_key]):
            entry[gloss_key] = deduplicate(entry[gloss_key] + variant[gloss_key])
            if variant[gloss_key] != entry[gloss_key]:
                log.warning(
                    f"""The entry {entry_repr(entry["ID"])} is stored as having a different meaning than its variant {entry_repr(variant["ID"])}"""
                )
        else:
            log.debug(
                f"""inheriting gloss from {entry_repr(entry["ID"])} for {entry_repr(variant["ID"])}"""
            )
            variant[gloss_key] = entry[gloss_key]
        variant["Parameter_ID"] = entry["Parameter_ID"]
        entry[obj_key].append(variant[obj_key])
        variant["Variant_ID"] = variant["ID"]
        variant["Morpheme_ID"] = entry["ID"]
        variant["ID"] = f"""{entry["ID"]}-{var_count+i}"""
        new_variant_morphs.append(variant)

    morphs = pd.DataFrame.from_dict(morph_list)

    new_variant_morphs = []
    for entry in entries.to_dict("records"):
        var_count = 1
        if check_variants and isinstance(entry[var_key], list):
            for variant in entry[var_key]:
                var_count += 1
                entry[obj_key].append(variant)
        if entry["ID"] in var_dict:
            for i, variant in enumerate(var_dict[entry["ID"]]):
                variant = variant.copy()
                process_variant(
                    entry, variant, new_variant_morphs, var_dict, var_count, i
                )

    new_variant_morphs = pd.DataFrame.from_dict(new_variant_morphs)

    if len(new_variant_morphs) > 0:
        morphs = morphs[~(morphs["Morpheme_ID"].isin(new_variant_morphs["Variant_ID"]))]
        morphs = pd.concat([morphs, new_variant_morphs])
    morphs["Language_ID"] = obj_lg
    morphs.rename(
        columns={obj_key: "Form", gloss_key: "Gloss", "morph-type": "Type"},
        inplace=True,
    )

    for col in entries.columns:
        if "variant-type" not in col:
            continue
        variants = entries[~(pd.isnull(entries[col]))]
        entries = entries.loc[~(entries.index.isin(variants.index))]

    entries[obj_key] = entries[obj_key].apply(sorted)
    entries[obj_key] = entries[obj_key].apply(deduplicate)
    entries = delistify(entries, sep)
    entries["Language_ID"] = obj_lg

    morphemes = entries.copy()
    morphemes = morphemes[(~(morphemes["morph-type"].isin(["phrase"])))]
    morphemes.rename(
        columns={
            gloss_key: "Gloss",
            definition_key: "Meaning",
            obj_key: "Form",
            "morph-type": "Type",
        },
        inplace=True,
    )
    morphs = morphs[(morphs["Morpheme_ID"].isin(list(morphemes["ID"])))]

    sentence_path = Path(output_dir / "sentences.csv")
    ref_pattern = re.compile(r"^(\d+.\d)+$")
    if dictionary_examples:
        if sentence_path.is_file():
            log.info(
                f"Found {sentence_path.resolve()}, adding segmentation to examples"
            )
            glossed_examples = pd.read_csv(
                sentence_path, dtype=str, keep_default_na=False
            )
            juicy_columns = ["Analyzed_Word", "Gloss"]
            glossed_examples.dropna(subset=juicy_columns, inplace=True)
            for col in juicy_columns:
                glossed_examples[col] = glossed_examples[col].apply(
                    lambda x: x.split("\t")
                )
            enriched_examples = []
            for ex in dictionary_examples:
                successful = False
                if " " in ex["source"]:
                    text_id, phrase_rec = ex["source"].split(" ")
                    if ref_pattern.match(phrase_rec):
                        rec, subrec = phrase_rec.split(".")
                        if subrec == "1":
                            subrec = ""
                        cands = glossed_examples[
                            (glossed_examples["Record_Number"] == rec)
                            & (glossed_examples["Phrase_Number"] == subrec)
                            & glossed_examples["Text_ID"].str.contains(text_id)
                        ]
                        if len(cands) == 1:
                            successful = True
                            enriched_examples.append(dict(cands.iloc[0]))
                        elif len(cands) > 1:
                            log.error(
                                f"Could not resolve ambiguous example reference [{text_id} {phrase_rec}]\n"
                                + cands.to_string()
                            )
                        else:
                            log.warning(
                                f"Could not resolve example reference [{text_id} {phrase_rec}]"
                            )
                if not successful:
                    enriched_examples.append(ex)
            dictionary_examples = pd.DataFrame.from_dict(enriched_examples)
        else:
            log.warning(
                f"There are dictionary examples. If you want to retrieve segmentation and glosses from the corpus, run cldflex flex2csv <your_file>.flextext and place sentences.csv in {output_dir.resolve()}"
            )
            dictionary_examples = pd.DataFrame.from_dict(dictionary_examples)
    else:
        dictionary_examples = pd.DataFrame.from_dict(dictionary_examples)

    dictionary_examples.fillna("", inplace=True)

    glottocode = conf.get("Glottocode", conf.get("Language_ID", None))
    with pd.option_context("mode.chained_assignment", None):
        if glottocode:
            for df in [unmodified_entries, morphemes, morphs, dictionary_examples]:
                df["Language_ID"] = glottocode
        else:
            for df in [unmodified_entries, morphemes, morphs, dictionary_examples]:
                df["Language_ID"] = obj_lg

    morphemes.fillna("", inplace=True)
    morphemes.to_csv(output_dir / "morphemes.csv", index=False)
    delistify(senses, sep)
    senses.to_csv(output_dir / "senses.csv", index=False)
    delistify(morphs, sep)
    morphs.drop_duplicates(
        subset=[x for x in morphs.columns if x != "ID"], inplace=True
    )  # entries may be "variants" of other entries in multiple ways

    morphs.to_csv(output_dir / "morphs.csv", index=False)

    unmodified_entries["Name"] = unmodified_entries[obj_key]
    delistify(unmodified_entries, sep)
    unmodified_entries.to_csv(output_dir / "entries.csv", index=False)
    if cldf:
        cldf_settings = conf.get("cldf", {})
        metadata = cldf_settings.get("metadata", {})
        if cldf_settings.get("lexicon", None) == "wordlist":
            unmodified_entries.rename(
                columns={gloss_key: "Meaning", obj_key: "Form"}, inplace=True
            )
            morphemes["Form"] = morphemes["Form"].apply(lambda x: x.split(sep))
            morphemes["Parameter_ID"] = morphemes["Parameter_ID"].apply(
                lambda x: x.split(sep)
            )
            tables = {
                "FormTable": morphemes,
                "ParameterTable": senses,
            }
            create_cldf(
                tables=tables,
                glottocode=glottocode,
                metadata=metadata,
                output_dir=output_dir,
                cwd=lift_file.parents[0],
            )
        else:
            create_dictionary_dataset(
                unmodified_entries,
                senses,
                metadata=metadata,
                examples=dictionary_examples,
                glottocode=glottocode,
                output_dir=output_dir,
                cwd=lift_file.parents[0],
            )

    return morphs

import logging
import os
import re
from itertools import chain
from pathlib import Path
from string import punctuation

import pandas as pd
import yaml
from bs4 import BeautifulSoup
from humidifier import get_values, humidify
from morphinder import Morphinder
from writio import dump

from cldflex import SEPARATOR
from cldflex.cldf import create_corpus_dataset
from cldflex.helpers import delistify, listify
from cldflex.lift2csv import convert as lift2csv

log = logging.getLogger(__name__)

delimiters = ["-", "<", ">", "~"]

punc = set(punctuation)


def compose_surface_string(entries):
    # combine surface words and punctuation into one string
    return "".join(w if set(w) <= punc else " " + w for w in entries).lstrip()


def init_word_dict(word, obj_key, punct_key, surface):
    """Create a dict containing the word-specific fields"""
    word_dict = {"morph_type": []}
    for word_item in word.find_all("item", recursive=False):
        key = word_item["type"] + "_" + word_item["lang"]
        if key in (obj_key, punct_key):
            surface.append(word_item.text)
        else:
            word_dict[key + "_word"] = word_item.text
    return word_dict


def extract_clitic_data(morpheme, morpheme_type, obj_key, gloss_key, conf):
    """Get annotations for clitics, fill in gaps with word-level information"""
    clitic_dict = {"morph_type": []}
    clitic_dict["morph_type"].append(morpheme_type)
    for item in morpheme.find_all("item"):
        key = item["type"] + "_" + item["lang"]
        clitic_dict.setdefault(key, "")
        clitic_dict[key] += item.text

    clitic_dict["Clitic_ID"] = humidify(
        clitic_dict.get(obj_key, "***") + "-" + clitic_dict.get(gloss_key, "***"),
        key="clitics",
    )
    clitic_dict.setdefault(
        f"pos_{conf['msa_lg']}_word",
        clitic_dict.get(f"msa_{conf['msa_lg']}", "<Not Sure>"),
    )
    # clitic_dict.setdefault(gloss_key + "_word", clitic_dict[gloss_key])
    return clitic_dict


def extract_morpheme_data(morpheme, morpheme_type, word_dict, gloss_key, conf):
    """Extract information from morphemes in a word, add to word_dict"""
    word_dict["morph_type"].append(morpheme_type)
    for item in morpheme.find_all("item"):
        key = item["type"] + "_" + item["lang"]
        word_dict.setdefault(key, "")
        text = item.text
        if key == gloss_key or "msa" in key:
            if (
                morpheme_type == "suffix"
                and not word_dict[key].endswith("-")
                and not text.startswith("-")
            ):
                text = "-" + item.text
            elif morpheme_type == "prefix" and not text.endswith("-"):
                text = item.text + "-"
            elif morpheme_type == "infix":
                if not text.startswith("-") and not word_dict[key].endswith("-"):
                    text = "-" + text
                if not text.endswith("-"):
                    text = text + "-"

        word_dict[key] += text


def iterate_morphemes(word, word_dict, obj_key, gloss_key, conf, p=False):
    """Go through morphemes of a word -- affixes are added to word_dict, clitics are handled separately"""
    proclitics = []
    enclitics = []
    morphs = word.find_all("morph")
    for morpheme in morphs:
        morpheme_type = morpheme.get("type", "root")
        if morpheme_type == "proclitic":
            clitic_dict = extract_clitic_data(
                morpheme, morpheme_type, obj_key, gloss_key, conf
            )
            if (
                len(morphs) == 1
            ):  # if this is a "p-word" consisting of only a clitic, put in place of word_dict instead
                word_dict = clitic_dict
            else:
                proclitics.append(clitic_dict)
        elif morpheme_type == "enclitic":
            clitic_dict = extract_clitic_data(
                morpheme, morpheme_type, obj_key, gloss_key, conf
            )
            if (
                len(morphs) == 1
            ):  # if this is a "p-word" consisting of only a clitic, put in place of word_dict instead
                word_dict = clitic_dict
            else:
                enclitics.append(clitic_dict)
        else:
            extract_morpheme_data(morpheme, morpheme_type, word_dict, gloss_key, conf)
    for key in [obj_key, gloss_key]:
        if word_dict and key not in word_dict:
            word_dict[key] = "=".join(
                [x.get(key) for x in proclitics] + [x.get(key) for x in enclitics]
            )
    return proclitics, enclitics, word_dict


def id_glosses(gloss, sep=None):
    res = [humidify(g, key="glosses") for g in re.split(r"\.\b", gloss)]
    if sep:
        return sep.join(res)
    return res


def get_form_slices(
    word_dict, word_id, lexicon, form_slices, obj_key, gloss_key, ex_id, retriever
):  # pylint: disable=too-many-arguments
    """For a given word consisting of a number of morphemes, establish what morphemes occur in which position, based on the lexicon information"""
    if word_id not in form_slices:
        form_slices[word_id] = []
        for m_c, (morph_obj, morph_gloss, morph_type) in enumerate(
            zip(
                re.split(re.compile("|".join(delimiters)), word_dict[obj_key]),
                re.split(re.compile("|".join(delimiters)), word_dict[gloss_key]),
                word_dict["morph_type"],
            )
        ):
            if morph_gloss:
                m_id, sense_id = retriever.retrieve_morph_id(
                    morph_obj,
                    morph_gloss,
                    morph_type,
                    sense_key="Parameter_ID",
                    form_key="Form_Bare",
                )
                if m_id:
                    form_slices[word_id].append(
                        {
                            "ID": f"{word_id}-{str(m_c)}",
                            "Wordform_ID": word_id,
                            "Form": re.sub(
                                "|".join(delimiters), "", word_dict[obj_key]
                            ),
                            "Form_Meaning": humidify(
                                word_dict[gloss_key].strip("="), key="meanings"
                            ),
                            "Morph_ID": m_id,
                            "Morpheme_Meaning": sense_id,
                            "Index": str(m_c),
                            "Gloss_ID": id_glosses(morph_gloss.strip("=")),
                        }
                    )
            else:
                log.warning(f"Unglossed morpheme /{morph_obj}/ in {ex_id}")


def process_clitic_slices(clitic, sentence_slices, gloss_key, word_count, ex_id):
    sentence_slices.append(
        {
            "ID": f"{ex_id}-{word_count}",
            "Example_ID": ex_id,
            "Wordform_ID": clitic["Clitic_ID"],
            "Index": word_count,
            "Form_Meaning": clitic.get(gloss_key, "***"),
            "Parameter_ID": humidify(
                clitic.get(gloss_key, "***").strip("="), key="meanings"
            ),
        }
    )
    return word_count + 1


def add_clitic_wordforms(wordforms, clitic, obj_key, gloss_key):
    wordforms.setdefault(
        clitic["Clitic_ID"],
        {"ID": clitic["Clitic_ID"], "Form": [], "Meaning": [], "Parameter_ID": []},
    )
    # print(clitic)
    # print(obj_key)
    if clitic[obj_key] not in wordforms[clitic["Clitic_ID"]]["Form"]:
        wordforms[clitic["Clitic_ID"]]["Form"].append(clitic[obj_key])
    if clitic[gloss_key].strip("=") not in wordforms[clitic["Clitic_ID"]]["Meaning"]:
        wordforms[clitic["Clitic_ID"]]["Meaning"].append(clitic[gloss_key].strip("="))
        humidify(clitic[gloss_key].strip("="), key="meanings")


def extract_records(  # noqa: MC0001
    text,
    obj_key,
    punct_key,
    gloss_key,
    text_id,
    wordforms,
    sentence_slices,
    form_slices,
    lexicon,
    conf,
):  # pylint: disable=too-many-locals,too-many-arguments
    record_list = []
    if lexicon is not None:
        retriever = Morphinder(lexicon)
    for phrase_count, phrase in enumerate(  # pylint: disable=too-many-nested-blocks
        text.find_all("phrase")
    ):
        surface = []
        segnum = phrase.select("item[type='segnum']")
        interlinear_lines = []
        if segnum:
            segnum = segnum[0].text
        else:
            segnum = phrase_count

        ex_id = humidify(f"{text_id}-{segnum}", key="examples", unique=True)
        log.debug(f"{ex_id}")

        word_count = 0
        for word in phrase.find_all("word"):
            word_id = word.get("guid", None)

            word_dict = init_word_dict(word, obj_key, punct_key, surface)

            proclitics, enclitics, word_dict = iterate_morphemes(
                word, word_dict, obj_key, gloss_key, conf
            )
            # sentence slices are only for analyzed word forms
            if word.find_all("morphemes"):
                if lexicon is not None and conf.get("form_slices", True):
                    get_form_slices(
                        word_dict,
                        word_id,
                        lexicon,
                        form_slices,
                        obj_key,
                        gloss_key,
                        ex_id,
                        retriever,
                    )
                    for clitic in proclitics + enclitics:
                        get_form_slices(
                            clitic,
                            clitic["Clitic_ID"],
                            lexicon,
                            form_slices,
                            obj_key,
                            gloss_key,
                            ex_id,
                            retriever,
                        )

                for clitic in proclitics:
                    word_count = process_clitic_slices(
                        clitic, sentence_slices, gloss_key, word_count, ex_id
                    )
                    add_clitic_wordforms(wordforms, clitic, obj_key, gloss_key)
                    del clitic["Clitic_ID"]
                    interlinear_lines.append(clitic)

                form_meaning = word_dict.get(gloss_key, "***").strip("=")
                form_meaning_id = humidify(form_meaning, key="meanings")

                sentence_slices.append(
                    {
                        "ID": f"{ex_id}-{word_count}",
                        "Example_ID": ex_id,
                        "Wordform_ID": word_id,
                        "Index": word_count,
                        "Form_Meaning": form_meaning,
                        "Parameter_ID": form_meaning_id,
                    }
                )
                word_count += 1
                if word_dict:
                    interlinear_lines.append(word_dict)
                    # add to wordform table
                    wordforms.setdefault(
                        word_id, {"ID": word_id, "Form": [], "Meaning": []}
                    )
                    word_dict[gloss_key] = word_dict[gloss_key]
                    for gen_col, label in [(obj_key, "Form"), (gloss_key, "Meaning")]:
                        if (
                            gen_col in word_dict
                            and word_dict[gen_col].strip("=")
                            not in wordforms[word_id][label]
                        ):
                            wordforms[word_id][label].append(
                                word_dict[gen_col].strip("=")
                            )
                for clitic in enclitics:
                    word_count = process_clitic_slices(
                        clitic, sentence_slices, gloss_key, word_count, ex_id
                    )
                    add_clitic_wordforms(wordforms, clitic, obj_key, gloss_key)
                    del clitic["Clitic_ID"]
                    interlinear_lines.append(clitic)
        surface = compose_surface_string(surface)
        interlinear_lines = pd.DataFrame.from_dict(interlinear_lines).fillna("")
        if len(interlinear_lines) != 0:
            interlinear_lines.drop(columns=["morph_type"], inplace=True)
        phrase_dict = {
            "ID": ex_id,
            "Primary_Text": surface,
            "Text_ID": text_id,
            "guid": phrase["guid"],
        }
        for attr, value in phrase.attrs.items():
            phrase_dict[attr] = value
        for phrase_item in phrase.find_all("item", recursive=False):
            phrase_dict[
                phrase_item["type"] + "_" + phrase_item["lang"] + "_phrase"
            ] = phrase_item.text
        for col in interlinear_lines.columns:
            if conf.get("fix_clitics", True):
                phrase_dict[col] = (
                    "\t".join(
                        interlinear_lines[
                            col
                        ]  # pylint: disable=unsubscriptable-object 🙄
                    )
                    .replace("\t=", "=")
                    .replace("=\t", "=")
                )
            else:
                phrase_dict[col] = "\t".join(
                    interlinear_lines[col]  # pylint: disable=unsubscriptable-object 🙄
                )
        record_list.append(phrase_dict)
    return record_list


def load_lexicon(lexicon_file, conf, sep, output_dir="."):
    if lexicon_file is None:
        log.warning(
            "No lexicon file provided. If you want the output to contain morph IDs, provide a csv file with ID, Form, and Meaning."
        )
        return None
    lexemes, stems, morphemes, morphs, senses = lift2csv(
        lift_file=lexicon_file, output_dir=output_dir, conf=conf
    )
    morphs["Form_Bare"] = morphs["Form"].apply(
        lambda x: re.sub(re.compile("|".join(delimiters)), "", x)
    )
    return lexemes, stems, morphemes, morphs, senses


def load_keys(conf, texts):
    if "gloss_lg" not in conf:
        log.info("Unconfigured: gloss_lg, assuming [en].")
        conf["gloss_lg"] = "en"
    if "msa_lg" not in conf:
        log.info(f"""Unconfigured: msa_lg, assuming [{conf["gloss_lg"]}].""")
        conf["msa_lg"] = conf["gloss_lg"]
    gloss_key = "gls_" + conf["gloss_lg"]

    if "obj_lg" not in conf:
        conf["obj_lg"] = texts.find_all("item", lang=lambda x: x != conf["gloss_lg"])[
            0
        ]["lang"]
        log.info(f"Unconfigured: obj_lg, assuming [{conf['obj_lg']}].")
    obj_key = "txt_" + conf["obj_lg"]
    punct_key = "punct_" + conf["obj_lg"]

    if "lang_id" not in conf:
        log.info(f"Unconfigured: lang_id, using [{conf['obj_lg']}]")
        conf["lang_id"] = conf["obj_lg"]
    return obj_key, gloss_key, punct_key


def get_text_id(text):
    text_id = None
    abbrevs = text.select("item[type='title-abbreviation']")
    for abbrev in abbrevs:
        if abbrev.text != "" and text_id is None:
            text_id = humidify(abbrev.text, key="texts", unique=True)
            log.debug(f"Processing text {text_id} ({abbrev['lang']})")
    return text_id


def get_text_metadata(text, text_id):
    text_metadata = {"ID": text_id}
    for text_item in text.find_all("item", recursive=False):
        key = text_item["type"] + "_" + text_item["lang"]
        text_metadata[key] = text_item.text
    return text_metadata


def split_subrecords(rec):
    if "." in rec["Sentence_Number"]:
        rec["Sentence_Number"], rec["Phrase_Number"] = rec["Sentence_Number"].split(".")
    return rec


def strip_form(form):
    return re.sub(re.compile("|".join(delimiters + ["Ø"])), "", form)


def prepare_records(df, conf):
    rename_dict = conf.get("mappings", {})
    for gen_col, label in [
        (f"gls_{conf['gloss_lg']}_phrase", "Translated_Text"),
        (f"pos_{conf['gloss_lg']}_word", "Part_Of_Speech"),
        (f"segnum_{conf['gloss_lg']}_phrase", "Sentence_Number"),
    ]:
        if label not in rename_dict.values():
            rename_dict.setdefault(gen_col, label)
    for k, v in rename_dict.items():
        if k not in df.columns:
            continue
        if v in df.columns:
            log.warning(
                f"Renaming '{k}' to '{v}' is overwriting an existing column '{v}'"
            )
        df[v] = df[k]
    df["Language_ID"] = conf["lang_id"]
    # resolve records with multiple phrases
    df = df.apply(lambda x: split_subrecords(x), axis=1)
    sort_order = [
        "ID",
        "Primary_Text",
        "Analyzed_Word",
        "Gloss",
        "Translated_Text",
        "Part_Of_Speech",
        "Text_ID",
        "Sentence_Number",
        "Phrase_Number",
        "Language_ID",
    ]
    sorted_cols = [x for x in sort_order if x in df.columns] + [
        x for x in df.columns if x not in sort_order
    ]
    df = df[sorted_cols]
    return df.fillna("")


def convert(
    flextext_file,
    lexicon_file=None,
    conf=None,
    output_dir=None,
    cldf=False,
    audio_folder=None,
):  # pylint: disable=too-many-locals,too-many-arguments
    output_dir = output_dir or Path(".")
    flextext_file = Path(flextext_file)
    log.debug(f"reading {flextext_file.resolve()}")
    with open(flextext_file, "r", encoding="utf-8") as f:
        texts = BeautifulSoup(f.read(), features="lxml")

    if not conf:
        log.info(
            "Running in unconfigured mode. Create a cldflex.yaml file, point to another --conf file, or pass in a conf dict to modify parameters."
        )
        conf = {}
    obj_key, gloss_key, punct_key = load_keys(conf, texts)
    sep = conf.get("csv_cell_separator", SEPARATOR)

    if lexicon_file:
        lexemes, stems, morphemes, lexicon, senses = load_lexicon(
            lexicon_file, conf, sep, output_dir
        )
    else:
        lexicon = None
        stems = None
        senses = None

    if lexicon is not None:
        lookup_lexicon = lexicon.copy()
        for col in lookup_lexicon.columns:
            if isinstance(lookup_lexicon[col].iloc[0], list) and col != "Parameter_ID":
                lookup_lexicon[col] = lookup_lexicon[col].apply(lambda x: sep.join(x))
    else:
        lookup_lexicon = None

    wordforms = {}
    sentence_slices = []
    form_slices = {}
    text_list = []
    record_list = []
    for text in texts.find_all("interlinear-text"):
        text_id = get_text_id(text)
        text_list.append(get_text_metadata(text, text_id))

        record_list.extend(
            extract_records(
                text,
                obj_key,
                punct_key,
                gloss_key,
                text_id,
                wordforms,
                sentence_slices,
                form_slices,
                lookup_lexicon,
                conf,
            )
        )

    df = (
        pd.DataFrame.from_dict(record_list)
        .rename(columns={obj_key: "Analyzed_Word", gloss_key: "Gloss"})
        .fillna("")
    )
    records = prepare_records(df, conf)
    wordforms = pd.DataFrame.from_dict(wordforms.values())
    texts = pd.DataFrame.from_dict(text_list)
    texts.rename(columns={"title_" + conf["gloss_lg"]: "Name"}, inplace=True)
    form_slices = pd.DataFrame.from_dict(chain(*form_slices.values()))
    tables = {
        "wordforms": wordforms,
        "examples": records,
        "texts": texts,
    }
    if len(form_slices) > 0:
        tables["wordformparts"] = form_slices

    if conf.get("sentence_slices", True):
        sentence_slices = pd.DataFrame.from_dict(sentence_slices)
        tables["exampleparts"] = sentence_slices

    if cldf:
        if audio_folder:
            tables["media"] = pd.DataFrame.from_dict(
                [
                    {
                        "ID": f.stem,
                        "Media_Type": "audio/" + f.suffix.strip("."),
                        "Download_URL": str(f),
                    }
                    for f in audio_folder.iterdir()
                ]
            )
        cldf_settings = conf.get("cldf", {})
        metadata = cldf_settings.get("metadata", {})

        tables["examples"] = listify(tables["examples"], "Analyzed_Word", "\t")
        tables["examples"] = listify(tables["examples"], "Gloss", "\t")

        if stems is not None:
            stems["Gloss_ID"] = stems["Gloss"].apply(
                lambda x: [humidify(x, key="glosses")]
            )

        glosses = get_values("glosses")
        if glosses:
            tables["glosses"] = pd.DataFrame.from_dict(
                [{"ID": v, "Name": k if k else "unknown"} for k, v in glosses.items()]
            )

        delistify(tables["wordforms"], ",")
        tables["wordforms"]["Morpho_Segments"] = tables["wordforms"]["Form"].apply(
            lambda x: x.split("-")
        )
        tables["wordforms"]["Form"] = tables["wordforms"]["Form"].apply(strip_form)
        tables["wordforms"]["Description"] = tables["wordforms"]["Meaning"]

        contributors = cldf_settings.get("contributors", {})
        if contributors:
            for contributor in contributors:
                if "id" not in contributor and "name" in contributor:
                    contributor["ID"] = humidify(
                        contributor["name"], key="contr", unique=True
                    )
                else:
                    contributor["ID"] = contributor["id"]
                for k in contributor.keys():
                    if k != "ID":
                        contributor[k.capitalize()] = contributor.pop(k)
            tables["contributors"] = pd.DataFrame.from_dict(contributors)
        if lexicon is not None:
            stems["Description"] = stems["Gloss"]
            lexicon["Description"] = lexicon["Gloss"]
            morphemes = morphemes.copy()
            morphemes["Description"] = morphemes["Gloss"]
            tables["stems"] = stems
            tables["lexemes"] = lexemes
            tables["morphs"] = lexicon
            tables["morphemes"] = morphemes
            with pd.option_context("mode.chained_assignment", None):
                for namedf in [lexicon, morphemes, stems, lexemes]:
                    if "Form" in namedf:
                        namedf.rename(columns={"Form": "Name"}, inplace=True)

        param_dict = get_values("meanings")
        wordforms["Parameter_ID"] = wordforms["Meaning"].map(param_dict)
        wf_senses = pd.DataFrame.from_dict(
            [{"ID": v, "Name": k} for k, v in param_dict.items()]
        )
        senses = pd.concat([senses, wf_senses]).fillna("")
        tables["senses"] = senses

        glottocode = conf.get("glottocode", None)
        if not glottocode:
            iso = conf["lang_id"]
        else:
            iso = None
        create_corpus_dataset(
            tables=tables,
            glottocode=glottocode,
            iso=iso,
            metadata=metadata,
            output_dir=output_dir,
            cwd=flextext_file.parents[0],
            sep=sep,
        )

    for name, df in tables.items():
        df = delistify(df, sep)
        if output_dir:
            dump(df, output_dir / f"{name}.csv")
    return tables

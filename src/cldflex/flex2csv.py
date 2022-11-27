import logging
import os
import re
from pathlib import Path
from string import punctuation
import pandas as pd
import yaml
from bs4 import BeautifulSoup
from slugify import slugify
from cldflex.helpers import LexiconRetriever
from cldflex.helpers import slug
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

    clitic_dict["ID"] = slug(
        clitic_dict.get(obj_key, "***") + "-" + clitic_dict.get(gloss_key, "***")
    )
    clitic_dict.setdefault(
        f"pos_{conf['msa_lg']}_word",
        clitic_dict.get(f"msa_{conf['msa_lg']}", "<Not Sure>"),
    )
    clitic_dict[gloss_key] = clitic_dict[gloss_key]
    clitic_dict.setdefault(gloss_key + "_word", clitic_dict[gloss_key])
    return clitic_dict


def extract_morpheme_data(morpheme, morpheme_type, word_dict, gloss_key, conf):
    """Extract information from morphemes in a word, add to word_dict"""
    word_dict["morph_type"].append(morpheme_type)
    for item in morpheme.find_all("item"):
        key = item["type"] + "_" + item["lang"]
        word_dict.setdefault(key, "")
        text = item.text
        if key in [gloss_key, f"msa_{conf['gloss_lg']}"]:
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


def iterate_morphemes(word, word_dict, obj_key, gloss_key, conf):
    """Go through morphemes of a word -- affixes are added to word_dict, clitics are handled separately"""
    proclitics = []
    enclitics = []
    for morpheme in word.find_all("morph"):
        morpheme_type = morpheme.get("type", "root")
        if morpheme_type == "proclitic":
            proclitics.append(
                extract_clitic_data(morpheme, morpheme_type, obj_key, gloss_key, conf)
            )
        elif morpheme_type == "enclitic":
            enclitics.append(
                extract_clitic_data(morpheme, morpheme_type, obj_key, gloss_key, conf)
            )
        else:
            extract_morpheme_data(morpheme, morpheme_type, word_dict, gloss_key, conf)
    for key in [obj_key, gloss_key]:
        if key not in word_dict:
            word_dict[key] = "=".join(
                [x[key] for x in proclitics] + [x[key] for x in enclitics]
            )
    return proclitics, enclitics


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
                m_id, sense_id = retriever.retrieve_morpheme_id(
                    morph_obj, morph_gloss, lexicon, morph_type, ex_id
                )
                if m_id:
                    form_slices[word_id].append(
                        {
                            "ID": f"{word_id}-{str(m_c)}",
                            "Form_ID": word_id,
                            "Form": re.sub(
                                "|".join(delimiters), "", word_dict[obj_key]
                            ),
                            "Form_Meaning": slug(word_dict[gloss_key]),
                            "Morph_ID": m_id,
                            "Morpheme_Meaning": sense_id,
                            "Index": str(m_c),
                        }
                    )
            else:
                log.warning(f"Unglossed morpheme /{morph_obj}/ in {ex_id}")


def process_clitic_slices(clitic, sentence_slices, gloss_key, word_count, ex_id):
    sentence_slices.append(
        {
            "ID": f"{ex_id}-{word_count}",
            "Example_ID": ex_id,
            "Form_ID": clitic["ID"],
            "Index": word_count,
            "Form_Meaning": clitic.get(gloss_key, "***"),
            "Parameter_ID": slug(clitic.get(gloss_key, "***")),
        }
    )
    return word_count + 1


def add_clitic_wordforms(wordforms, clitic, obj_key, gloss_key):
    wordforms.setdefault(clitic["ID"], {"ID": clitic["ID"], "Form": [], "Meaning": []})
    if obj_key in clitic and clitic[obj_key] not in wordforms[clitic["ID"]]["Form"]:
        wordforms[clitic["ID"]]["Form"].append(clitic[obj_key])
    if (
        gloss_key in clitic
        and clitic[gloss_key].strip("=") not in wordforms[clitic["ID"]]["Meaning"]
    ):
        wordforms[clitic["ID"]]["Meaning"].append(clitic[gloss_key].strip("="))


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
    retriever = LexiconRetriever()

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

        ex_id = slugify(f"{text_id}-{segnum}")
        log.debug(f"{ex_id}")

        word_count = 0
        for word in phrase.find_all("word"):
            word_id = word.get("guid", None)

            word_dict = init_word_dict(word, obj_key, punct_key, surface)
            proclitics, enclitics = iterate_morphemes(
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
                            clitic["ID"],
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
                    del clitic["ID"]
                    interlinear_lines.append(clitic)

                form_meaning = word_dict.get(gloss_key, "***")
                form_meaning_id = slug(form_meaning)

                sentence_slices.append(
                    {
                        "ID": f"{ex_id}-{word_count}",
                        "Example_ID": ex_id,
                        "Form_ID": word_id,
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
                    for gen_col, label in [(obj_key, "Form"), (gloss_key, "Meaning")]:
                        if (
                            gen_col in word_dict
                            and word_dict[gen_col] not in wordforms[word_id][label]
                        ):
                            wordforms[word_id][label].append(word_dict[gen_col])

                for clitic in enclitics:
                    word_count = process_clitic_slices(
                        clitic, sentence_slices, gloss_key, word_count, ex_id
                    )
                    add_clitic_wordforms(wordforms, clitic, obj_key, gloss_key)
                    del clitic["ID"]
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
            phrase_dict[col] = (
                "\t".join(
                    interlinear_lines[col]  # pylint: disable=unsubscriptable-object 🙄
                )
                .replace("\t=", "=")
                .replace("=\t", "=")
            )
        record_list.append(phrase_dict)
    return record_list


def load_lexicon(lexicon_file, conf, sep, output_dir="."):
    if lexicon_file is None:
        log.warning(
            "No lexicon file provided. If you want the output to contain morph IDs, provide a csv file with ID, Form, and Meaning."
        )
        return None
    if lexicon_file.suffix == ".lift":
        lexicon = lift2csv(lift_file=lexicon_file, output_dir=output_dir, conf=conf)
    elif lexicon_file.suffix == ".csv":
        log.info(f"Reading lexicon file {lexicon_file.resolve()}")
        lexicon = pd.read_csv(lexicon_file, encoding="utf-8", keep_default_na=False)
    else:
        log.error(f"Please specify a .csv or .lift file ({lexicon_file})")
        return None
    lexicon["Form_Bare"] = lexicon["Form"].apply(
        lambda x: re.sub(re.compile("|".join(delimiters)), "", x)
    )
    for split_col in ["Form_Bare", "Form", "Gloss", "Parameter_ID"]:
        lexicon[split_col] = lexicon[split_col].apply(lambda x: x.split(sep))
    morpheme_lg = lexicon.iloc[0]["Language_ID"]
    if morpheme_lg != conf["Language_ID"]:
        log.info(
            f"Changing language ID from [{morpheme_lg}] to [{conf['Language_ID']}]"
        )
        lexicon["Language_ID"] = conf["Language_ID"]
    return lexicon


def load_keys(conf, texts):
    if "gloss_lg" not in conf:
        log.info("No glossing language specified, assuming [en].")
        conf["gloss_lg"] = "en"
    if "msa_lg" not in conf:
        conf["msa_lg"] = conf["gloss_lg"]
    gloss_key = "gls_" + conf["gloss_lg"]

    if "obj_lg" not in conf:
        conf["obj_lg"] = texts.select(f"item[lang!={conf['gloss_lg']}]")[0]["lang"]
        log.info(f"No object language specified, assuming [{conf['obj_lg']}].")
    obj_key = "txt_" + conf["obj_lg"]
    punct_key = "punct_" + conf["obj_lg"]

    if "Language_ID" not in conf:
        log.info(f"Language_ID not specified, using [{conf['obj_lg']}]")
        conf["Language_ID"] = conf["obj_lg"]
    return obj_key, gloss_key, punct_key


def get_text_id(text):
    text_id = None
    abbrevs = text.select("item[type='title-abbreviation']")
    for abbrev in abbrevs:
        if abbrev.text != "" and text_id is None:
            text_id = slugify(abbrev.text)
            log.info(f"Read text {text_id} ({abbrev['lang']})")
    return text_id


def get_text_metadata(text, text_id):
    text_metadata = {"ID": text_id}
    for text_item in text.find_all("item", recursive=False):
        key = text_item["type"] + "_" + text_item["lang"]
        text_metadata[key] = text_item.text
    return text_metadata


def write_form_slices(form_slices, output_dir):
    all_slices = []
    for slices in form_slices.values():
        for form_slice in slices:
            all_slices.append(form_slice)
    form_slices = pd.DataFrame.from_dict(all_slices)
    if len(form_slices) > 0:
        log.debug(f"Saving {(output_dir / 'form_slices.csv').resolve()}")
        form_slices.to_csv(output_dir / "form_slices.csv", index=False)
    return form_slices


def split_part_col(rec):
    if "." in rec["Record_Number"]:
        rec["Record_Number"], rec["Phrase_Number"] = rec["Record_Number"].split(".")
    return rec


def write_sentences(df, output_dir, conf):
    rename_dict = conf.get("mappings", {})
    for gen_col, label in [
        (f"gls_{conf['gloss_lg']}_phrase", "Translated_Text"),
        (f"pos_{conf['gloss_lg']}_word", "Part_Of_Speech"),
        (f"segnum_{conf['gloss_lg']}_phrase", "Record_Number"),
    ]:
        rename_dict.setdefault(gen_col, label)
    for k, v in rename_dict.items():
        if v in df.columns:
            log.warning(
                f"Renaming '{k}' to '{v}' is overwriting an existing column '{v}'"
            )
        df.rename(columns={k: v}, inplace=True)
    df["Language_ID"] = conf["Language_ID"]
    # resolve records with multiple phrases
    df = df.apply(lambda x: split_part_col(x), axis=1)
    log.debug(type(output_dir))
    sort_order = [
        "ID",
        "Primary_Text",
        "Analyzed_Word",
        "Gloss",
        "Translated_Text",
        "Part_Of_Speech",
        "Text_ID",
        "Record_Number",
        "Phrase_Number",
        "Language_ID",
    ]
    sorted_cols = [x for x in sort_order if x in df.columns] + [x for x in df.columns if x not in sort_order]
    df = df[sorted_cols]
    log.debug(f"Saving {(output_dir / 'sentences.csv').resolve()}")
    df.to_csv(output_dir / "sentences.csv", index=False)
    return df.fillna("")


def write_wordforms(wordforms, output_dir, conf, sep):
    wordforms = pd.DataFrame.from_dict(wordforms.values())
    lg_id = conf.get("Language_ID", None)
    if lg_id:
        wordforms["Language_ID"] = lg_id
    for col in ["Form", "Meaning"]:
        wordforms[col] = wordforms[col].apply(
            lambda x: sep.join(x)  # pylint: disable=unnecessary-lambda 🙄
        )
    log.debug(f"Saving {(output_dir / 'wordforms.csv').resolve()}")
    wordforms.to_csv(output_dir / "wordforms.csv", index=False)
    return wordforms


def write_generic(data, name, output_dir):
    df = pd.DataFrame.from_dict(data)
    log.debug(f"Saving {(output_dir / f'{name}.csv').resolve()}")
    df.to_csv(output_dir / f"{name}.csv", index=False)
    return df


def convert(
    flextext_file,
    lexicon_file=None,
    config_file=None,
    output_dir=None,
    conf=None,
    cldf=False,
):  # pylint: disable=too-many-locals,too-many-arguments
    output_dir = output_dir or Path(os.path.dirname(os.path.realpath(flextext_file)))
    log.info(f"Reading {flextext_file.resolve()}")
    with open(flextext_file, "r", encoding="utf-8") as f:
        texts = BeautifulSoup(f.read(), features="lxml")

    if not conf:
        if not config_file:
            log.warning("No configuration file or dict provided.")
            conf = {}
        else:
            with open(config_file, encoding="utf-8") as f:
                conf = yaml.safe_load(f)
    obj_key, gloss_key, punct_key = load_keys(conf, texts)
    sep = conf.get("csv_cell_separator", "; ")
    lexicon = load_lexicon(lexicon_file, conf, sep, output_dir)

    wordforms = {}

    sentence_slices = []
    form_slices = {}
    text_list = []
    record_list = []
    for text in texts.find_all("interlinear-text"):
        text_id = get_text_id(text)
        log.debug(f"Processing {text_id}")
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
                lexicon,
                conf,
            )
        )

    df = (
        pd.DataFrame.from_dict(record_list)
        .rename(columns={obj_key: "Analyzed_Word", gloss_key: "Gloss"})
        .fillna("")
    )

    df = write_sentences(df, output_dir, conf)

    wordforms = write_wordforms(wordforms, output_dir, conf, sep)

    if conf.get("sentence_slices", True):
        sentence_slices = write_generic(sentence_slices, "sentence_slices", output_dir)

    texts = write_generic(text_list, "texts", output_dir)

    form_slices = write_form_slices(form_slices, output_dir)

    log.info(f"Wrote CSV files to {output_dir.resolve()}")
    if cldf:
        from cldflex.cldf import create_cldf  # pylint: disable=import-outside-toplevel

        cldf_settings = conf.get("cldf", {})
        metadata = cldf_settings.get("metadata", {})
        tables = {"FormTable": wordforms, "ExampleTable": df, "TextTable": texts}
        contributors = cldf_settings.get("contributors", {})
        if contributors:
            for contributor in contributors:
                if "id" not in contributor and "name" in contributor:
                    contributor["ID"] = slugify(contributor["name"])
                else:
                    contributor["ID"] = contributor["id"]
                for k in contributor.keys():
                    if k != "ID":
                        contributor[k.capitalize()] = contributor.pop(k)
            tables["ContributorTable"] = pd.DataFrame.from_dict(contributors)
        if conf.get("sentence_slices", True):
            tables["SentenceSlices"] = sentence_slices
        if lexicon is not None:
            lexicon["Name"] = lexicon["Form_Bare"].apply(
                lambda x: sep.join(x)  # pylint: disable=unnecessary-lambda 🙄
            )
            tables["MorphTable"] = lexicon
            if conf.get("form_slices", True):
                tables["FormSlices"] = form_slices
            tables["MorphsetTable"] = load_lexicon(
                output_dir / "morphemes.csv", conf, sep
            )
            # tables["MorphsetTable"] = morphemes["Parameter_ID"] = morphemes["Parameter_ID"].apply(lambda x: x.split(sep))
            tables["ParameterTable"] = pd.read_csv(output_dir / "senses.csv")

        glottocode = conf.get("Glottocode", None)
        if not glottocode:
            log.warning("You have not specified a glottocode in your configuration.")
            iso = conf.get("Language_ID", None)
        else:
            iso = None
        create_cldf(
            tables=tables,
            glottocode=glottocode,
            iso=iso,
            metadata=metadata,
            output_dir=output_dir,
            cwd=flextext_file.parents[0],
        )

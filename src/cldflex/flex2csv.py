from xml.etree.ElementTree import fromstring
from xmljson import badgerfish as bf
import sys
import os
import csv
import re
import logging
import yaml
from slugify import slugify
from clldutils.loglib import get_colorlog
from cldflex.helpers import listify
import pandas as pd
import numpy as np
from json import loads, dumps


def to_dict(input_ordered_dict):
    return loads(dumps(input_ordered_dict))


log = get_colorlog(__name__, sys.stdout, level=logging.DEBUG)

delimiters = ["-", "="]

# This splits an object word into its morphemes
# e.g. "apa-ne" -> ["apa", "-", "ne"]
def split_obj_word(word):
    output = []
    char_list = list(word)
    for i, char in enumerate(char_list):
        if len(output) == 0 or (char in delimiters or output[-1] in delimiters):
            output.append(char)
        else:
            output[-1] += char
    return output


# compare forms, ignoring spaces, periods and delimiters
def form_match(str1, str2):
    var1 = [
        str1,
        str1.replace(".", " "),
        str1.replace(" ", ""),
        str1.replace("-", ""),
        str1.replace("=", ""),
    ]
    var2 = [
        str2,
        str2.replace(".", " "),
        str2.replace(" ", ""),
        str2.replace("-", ""),
        str2.replace("=", ""),
    ]
    return list(set(var1) & set(var2)) != []


def search_lexicon(form, meaning):
    if len(lexicon) == 0:
        return "X"
    new_meaning = meaning
    for morph_id, morpheme in lexicon.items():
        lex_forms = []
        for lex_form in morpheme["forms"]:
            for sub_meaning in morpheme["meanings"]:
                if form_match(form, lex_form) and form_match(new_meaning, sub_meaning):
                    return morph_id
    return "X"


def extract_flex_record(
    example,
    text_id,
    obj_lg="",
    gloss_lg="",
    fallback_exno="1",
    column_mappings={},
    drop_columns=[],
    conf={},
):
    phrase_data = {}
    for i in example:
        if i in ["item", "words"]:
            continue
        phrase_data[i.strip("@")] = example[i]

    if "item" in example:
        for entry in example["item"]:
            if "$" in entry:
                phrase_data[entry["@type"] + "_" + entry["@lang"]] = entry["$"]

    segnum = phrase_data.get(f"segnum_{gloss_lg}", None)
    if segnum:
        ex_id = slugify(f"{text_id}-{segnum}")
    else:
        exno = fallback_exno
        ex_id = slugify(f"{text_id}-{exno}")

    # this is the expected key for surface forms
    surf_key = "word_txt_" + obj_lg  # <item type="txt" lang="mdc">Yabi</item>
    punct_key = "word_punct_" + obj_lg  # <item type="punct" lang="mdc">.</item>

    surf_sentence = []
    word_datas = []

    words = listify(example["words"]["word"])

    # log.debug(dict(words[0]))

    for word_count, word_data in enumerate(words):
        word_data = dict(word_data)
        # log.debug(word_data)
        wf_id = word_data.get("@guid", f"{ex_id}-{word_count}")
        # log.debug(wf_id)

        # 'item' in flextext are surface form (including punctuation), glosses and POS
        if "item" in word_data:
            word_items = listify(word_data["item"])
            for entry in word_items:
                typ = entry["@type"]
                field_key = "word" + "_" + typ + "_" + entry["@lang"]
                if field_key.startswith("word_txt") or field_key.startswith(
                    "word_punct"
                ):
                    word_data["surface"] = entry["$"]
                else:
                    word_data[field_key] = entry.get("$", "")

        if "morphemes" in word_data:
            morphemes = listify(word_data["morphemes"]["morph"])
            for morpheme in morphemes:
                m_type = morpheme.get("@type", "root")
                if "morph_type" not in word_data:
                    word_data["morph_type"] = []
                word_data["morph_type"].append(m_type)
                items = listify(
                    morpheme["item"]
                )  # morphs, underlying forms ("lexemes"), glosses, POS
                for item in items:
                    value = item.get("$", "MISSING")
                    item_key = item["@type"] + "_" + item["@lang"]
                    if item_key.startswith(
                        "hn_"
                    ):  # subscripts for distinguishing homophones
                        word_data[item_key.replace("hn_", "cf_")][-1] += str(value)
                    else:
                        word_data.setdefault(item_key, [])
                        word_data[item_key].append(str(value))

        word_datas.append(word_data)
    ex_df = pd.DataFrame.from_dict(word_datas)
    ex_df.drop(columns=["morphemes", "item"], inplace=True)

    word_cols = [
        x for x in ex_df.columns if x.startswith("word_") or x in ["@guid", "surface"]
    ]
    word_cols = ex_df[word_cols]

    morph_cols = [x for x in ex_df.columns if not x in word_cols.columns]
    morph_cols = ex_df[morph_cols].copy()
    morph_cols.dropna(how="all", inplace=True)

    obj_key = "txt_" + obj_lg
    gloss_key = "gls_" + gloss_lg
    morpheme_ids = []
    gloss_out = []

    for i, word in morph_cols.iterrows():
        if gloss_key not in word or word[gloss_key] is np.nan:
            log.warning(
                f"No gloss line ({gloss_key}) found for word {''.join(word[obj_key])} "
            )
            morpheme_ids.append("X")
        else:
            for o, g in zip(word[obj_key], word[gloss_key]):
                morpheme_ids.append(search_lexicon(o, g))
        # add "-" where not present
        fixed_gloss = []
        for gloss, morph_type in zip(word[gloss_key], word["morph_type"]):
            if morph_type == "suffix" and not gloss.startswith("-"):
                gloss = "-" + gloss
            elif morph_type == "prefix" and not gloss.endswith("-"):
                gloss += "-"
            fixed_gloss.append(gloss)
        gloss_out.append("".join(fixed_gloss))

    morph_cols.fillna("", inplace=True)
    # print(morph_cols)
    if len(morph_cols) == 0:
        log.warning(f"{ex_id} has no glossing")
        morph_cols[gloss_key] = ""
    else:
        for gloss_col in [obj_key, gloss_key]:
            if gloss_col in morph_cols:
                morph_cols[gloss_col] = morph_cols[gloss_col].apply(
                    lambda x: "".join(x)
                )
            else:
                morph_cols[gloss_col] = ""

    print(phrase_data)
    out_dict = {
        "ID": ex_id,
        conf.get("segmented_obj_label", "Primary_Text"): surf_sentence,
        conf.get("segmented_obj_label", "Analyzed_Word"): " ".join(morph_cols[obj_key]),
        conf.get("gloss_label", "Gloss"): " ".join(gloss_out),
        "Text_ID": text_id,
    }

    for k, v in phrase_data.items():
        if k in column_mappings:
            new_key = column_mappings[k]
            # if new_key in out_dict:
            # log.debug(f"Replacing column {new_key} with {k} from conf file")
            out_dict[new_key] = v
        elif k not in drop_columns:
            out_dict[k] = v
    if "Translated_Text" in out_dict:
        out_dict["Translated_Text"] = out_dict["Translated_Text"].strip("‘").strip("’")
    return out_dict


# def ex_handler(type, value, tb):
#     log.exception(f"Uncaught exception: {value}")


# sys.excepthook = ex_handler


def convert(flextext_file="", lexicon_file=None, config_file=None):
    logging.basicConfig(
        filename=f"flex2csv_{os.path.splitext(flextext_file)[0]}.log",
        filemode="w",
        level="INFO",
        format="%(levelname)s::%(name)s::%(message)s",
    )
    if flextext_file == "":
        log.error("No .flextext file provided")
        return
    else:
        dir_path = os.path.dirname(os.path.realpath(flextext_file))
    if not config_file:
        log.warning(f"Running without a config file.")
        conf = {}
    else:
        conf = yaml.safe_load(open(config_file))
    global lexicon
    lexicon = {}
    if lexicon_file is None:
        log.warning(
            f"No lexicon file provided. If you want the output to contain morpheme IDs, provide a csv file with ID, Form, and Meaning"
        )
    elif ".csv" in lexicon_file:
        log.info("Adding lexicon from CSV file…")
        for row in csv.DictReader(open(lexicon_file)):
            lexicon[row["ID"]] = {
                "forms": row["Form"].split("; "),
                "meanings": row["Gloss_" + conf["gloss_lg"]].split("; "),
            }
    else:
        log.warning(f"{lexicon_file} is not a valid lexicon file format.")
    name = flextext_file.split("/")[-1].split(".")[0]
    csv_out = conf.get("output_file", dir_path + "/%s_from_flex.csv" % name)
    f = open(flextext_file, "r")
    content = f.read()
    example_list = []
    texts = bf.data(fromstring(content))["document"]["interlinear-text"]
    if type(texts) is not list:
        texts = [texts]
    texts = to_dict(texts)
    log.info(f"Parsing {len(texts)} texts…")
    for text_count, bs in enumerate(texts):
        metadata = {}
        if "item" not in bs:
            log.error(f"Text #{i+1} has no title or language information")
        else:
            if type(bs["item"]) is not list:
                title_unit = [bs["item"]]
            else:
                title_unit = bs["item"]
            for item in title_unit:
                lg = item["@lang"]
                if "$" not in item:
                    continue
                tent = item["$"].strip()
                if item["@type"] not in metadata:
                    metadata[item["@type"]] = {}
                if lg not in metadata[item["@type"]]:
                    metadata[item["@type"]][lg] = tent
                else:
                    metadata[item["@type"]][lg] += ", " + tent

        if "title-abbreviation" in metadata:
            abbr_lg = list(metadata["title-abbreviation"].keys())[0]
            if len(metadata["title-abbreviation"].keys()) > 1:
                log.info(f"Assuming that {abbr_lg} stores title-abbreviation info")
            text_abbr = slugify(metadata["title-abbreviation"][abbr_lg])
        else:
            text_abbr = "missing-text-id"

        if "title" in metadata:
            title_lg = list(metadata["title"].keys())[0]
            if len(metadata["title"].keys()) > 1:
                log.info(f"Assuming that {title_lg} stores title info")
            title = metadata["title"][title_lg]
        else:
            title = "_MISSING_"

        log.info(f"Parsing text {text_abbr} '{title}'")

        examples = listify(bs["paragraphs"]["paragraph"])

        for ex_cnt, example in enumerate(examples):
            # if ex_cnt != 3:
            #     continue
            ex_id = f"{text_abbr}-{ex_cnt+1}"
            log.debug(f"Parsing record {ex_id}")
            if len(example) == 0 or "phrases" not in example:
                log.warning(
                    f"Skipping {ex_id} (empty paragraph, will probably cause numbering mismatch)"
                )
                continue
            # print(example["phrases"])
            if "phrase" not in example["phrases"]:
                # example["phrases"]["phrase"] = example["phrases"]
                subexamples = listify(example["phrase"])
            else:
                subexamples = listify(example["phrases"]["phrase"])
            for subex_count, data in enumerate(subexamples):
                # print(subex_count, data)
                example_list.append(
                    extract_flex_record(
                        example=data,
                        text_id=text_abbr,
                        obj_lg=conf["obj_lg"],
                        gloss_lg=conf["gloss_lg"],
                        fallback_exno=str(ex_cnt) + "-" + str(subex_count),
                        column_mappings=conf["mappings"],
                        drop_columns=conf["delete"],
                        conf=conf,
                    )
                )
    ex_df = pd.DataFrame.from_dict(example_list)
    ex_df["Language_ID"] = conf["Language_ID"]
    ex_df.to_csv(csv_out, index=False)

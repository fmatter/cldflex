from xml.etree.ElementTree import fromstring
from xmljson import badgerfish as bf
import sys
import os
import csv
import re
import logging
import yaml
from clldutils.loglib import get_colorlog
from cldflex.helpers import listify
import pandas as pd
import numpy as np

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
):
    data = {}
    for i in example:
        if i in ["item", "words"]:
            continue
        data[i.strip("@")] = example[i]

    exno = fallback_exno
    ex_id = "%s-%s" % (text_id, str(exno).replace(".", "_"))

    if "item" in example:
        for entry in example["item"]:
            if "$" in entry:
                data[entry["@type"] + "_" + entry["@lang"]] = entry["$"]

    surf_key = "word_txt_" + obj_lg
    punct_key = "word_punct_" + obj_lg

    surf_sentence = ""
    word_datas = []

    words = listify(example["words"]["word"])

    for word_count, word in enumerate(words):
        word_data = {}
        # 'item' here are word-level forms, glossings or other annotations
        if "item" in word:
            word_items = listify(word["item"])
            for entry in word_items:
                typ = entry["@type"]
                field_key = "word" + "_" + typ + "_" + entry["@lang"]
                if field_key == surf_key:
                    surf_sentence += " " + entry["$"]
                elif field_key == punct_key:
                    surf_sentence += entry["$"]
                else:
                    word_data[field_key] = entry.get("$", "")

        if "morphemes" in word:
            morphemes = listify(word["morphemes"]["morph"])
            for morpheme in morphemes:
                morph_type = morpheme.get("@type", "root")
                if "morph_type" not in word_data:
                    word_data["morph_type"] = []
                word_data["morph_type"].append(morph_type)
                # the GUID that is contained here is ONLY the GUID of the morpheme type, not the morpheme itself!
                items = listify(morpheme["item"])
                for item in items:
                    if "$" in item:
                        typ = item["@type"]
                        if typ == "hn":
                            typ = "cf"
                        typ = typ + "_" + item["@lang"]
                        if typ not in word_data:
                            word_data[typ] = []
                        word_data[typ].append(str(item["$"]))

        word_datas.append(word_data)
    ex_df = pd.DataFrame.from_dict(word_datas)
    word_cols = [x for x in ex_df.columns if x.startswith("word_")]
    word_cols = ex_df[word_cols]

    morph_cols = [x for x in ex_df.columns if not x.startswith("word_")]
    morph_cols = ex_df[morph_cols].copy()
    morph_cols.dropna(how="all", inplace=True)

    obj_string = "txt_" + obj_lg
    gloss_string = "gls_" + gloss_lg
    obj_out = []
    morpheme_ids = []

    for i, row in morph_cols.iterrows():
        if gloss_string not in row or row[gloss_string] is np.nan:
            morpheme_ids.append("X")
        else:
            for o, g in zip(row[obj_string], row[gloss_string]):
                morpheme_ids.append(search_lexicon(o, g))
        # add "-" where not present
        fixed_obj = []
        for obj, morph_type in zip(row[obj_string], row["morph_type"]):
            if morph_type == "suffix" and not obj.startswith("-"):
                obj = "-" + obj
            elif morph_type == "prefix" and not obj.endswith("-"):
                obj += "-"
            fixed_obj.append(obj)
        obj_out.append("".join(fixed_obj))

    morph_cols.fillna("", inplace=True)
    # print(morph_cols)
    if len(morph_cols) == 0:
        log.warning(f"{ex_id} has no glossing")
        morph_cols[gloss_string] = ""
    else:
        for gloss_col in [obj_string, gloss_string]:
            if gloss_col in morph_cols:
                morph_cols[gloss_col] = morph_cols[gloss_col].apply(lambda x: "".join(x))
            else:
                morph_cols[gloss_col] = ""

    out_dict = {
        "ID": ex_id,
        "Sentence": surf_sentence,
        "Segmentation": " ".join(obj_out),
        "Gloss": " ".join(morph_cols[gloss_string]),
        "Text_ID": text_id,
        "Morpheme_IDs": "; ".join(morpheme_ids)
    }
    for k, v in data.items():
        if k in column_mappings:
            new_key = column_mappings[k]
            if new_key in out_dict:
                log.debug(f"Replacing column {new_key} with {k} from conf file")
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
        log.warning(f"No lexicon file provided. If you want the output to contain morpheme IDs, provide a csv file with ID, Form, and Meaning")
    elif ".csv" in lexicon_file:
        log.info("Adding lexicon from CSV file…")
        for row in csv.DictReader(open(lexicon_file)):
            lexicon[row["ID"]] = {
                "forms": row["Form"].split("; "),
                "meanings": row["Gloss_"+conf["gloss_lg"]].split("; "),
            }
    else:
        log.warning(
            f"{lexicon_file} is not a valid lexicon file format."
        )
    name = flextext_file.split("/")[-1].split(".")[0]
    csv_out = conf.get("output_file", dir_path + "/%s_from_flex.csv" % name)
    f = open(flextext_file, "r")
    content = f.read()
    example_list = []
    texts = bf.data(fromstring(content))["document"]["interlinear-text"]
    if type(texts) is not list:
        texts = [texts]
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
            text_abbr = metadata["title-abbreviation"][abbr_lg]
        else:
            text_abbr = "_MISSING_"

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
                example_list.append(
                    extract_flex_record(
                        example=data,
                        text_id=text_abbr,
                        obj_lg=conf["obj_lg"],
                        gloss_lg=conf["gloss_lg"],
                        fallback_exno=str(ex_cnt) + "." + str(subex_count),
                        column_mappings=conf["mappings"],
                        drop_columns=conf["delete"],
                    )
                )
    ex_df = pd.DataFrame.from_dict(example_list)
    ex_df["Language_ID"] = conf["Language_ID"]
    ex_df.to_csv(csv_out, index=False)
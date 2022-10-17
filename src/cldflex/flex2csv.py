from xml.etree.ElementTree import fromstring
from xmljson import badgerfish as bf
import os
import re
import logging
import yaml
from slugify import slugify
from cldflex.helpers import listify, retrieve_morpheme_id
import pandas as pd
import numpy as np
from pathlib import Path
from json import loads, dumps
from string import punctuation


def to_dict(input_ordered_dict):
    return loads(dumps(input_ordered_dict))


log = logging.getLogger(__name__)

delimiters = ["-", "=", "<", ">", "~"]

punc = set(punctuation)

# combine surface words and punctuation into one string
def compose_surface_string(entries):
    return "".join(w if set(w) <= punc else " " + w for w in entries).lstrip()


# This splits an object word into its morphemes
# e.g. "apa-ne" -> ["apa", "-", "ne"]
def split_obj_word(word):
    output = []
    char_list = list(word)
    for char in char_list:
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
    return list(set(var1) & set(var2))


def search_lexicon(form, meaning):
    if len(lexicon) == 0:
        return "X"
    new_meaning = meaning
    for morph_id, morpheme in lexicon.items():
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
    column_mappings=None,
    drop_columns=None,
    conf=None,
    lexicon=None,
    verbose=False,
):
    column_mappings = column_mappings or {}
    conf = conf or {}
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

    surf_sentence = []
    word_datas = []

    words = listify(example["words"]["word"])

    for word_count, word_data in enumerate(words):
        word_data = dict(word_data)
        # log.debug(word_data)
        # wf_id = word_data.get("@guid", f"{ex_id}-{word_count}")
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

    if f"word_pos_{gloss_lg}" not in ex_df.columns:
        ex_df[f"word_pos_{gloss_lg}"] = ""

    for col in ["morphemes", "item"]:
        if col in ex_df.columns:
            ex_df.drop(columns=[col], inplace=True)

    word_cols = [
        x for x in ex_df.columns if x.startswith("word_") or x in ["@guid", "surface"]
    ]
    word_cols = ex_df[word_cols]

    obj_key = "txt_" + obj_lg
    gloss_key = "gls_" + gloss_lg
    # word_gloss_key = "word_gls_{key}" % (conf.get("word_gloss_lg", conf["gloss_lg"]))

    if gloss_key not in ex_df.columns:
        ex_df[gloss_key] = "***"
    # if obj_key not in ex_df.columns:
    #     return {
    #         "ID": ex_id,
    #         conf.get("segmented_obj_label", "Primary_Text"): surf_sentence,
    #         conf.get("segmented_obj_label", "Analyzed_Word"): "",
    #         conf.get("gloss_label", "Gloss"): "",
    #         "Text_ID": text_id,
    #     }

    morph_cols = [x for x in ex_df.columns if x not in word_cols.columns]
    morph_cols = ex_df[morph_cols].copy()
    morph_cols.dropna(how="all", inplace=True)

    if obj_key in ex_df.columns:
        # put ["***"] instead of NaN
        for col in [gloss_key, obj_key, "morph_type"]:
            morph_cols[col].fillna("***", inplace=True)
            morph_cols[col] = morph_cols[col].apply(
                lambda x: [x] if not isinstance(x, list) else x
            )

        poses = []
        if "@guid" in ex_df.columns:
            ex_df[f"word_pos_{gloss_lg}"] = ex_df[f"word_pos_{gloss_lg}"].fillna("")
            for guid, pos in zip(ex_df["@guid"], ex_df[f"word_pos_{gloss_lg}"]):
                if pd.isnull(guid):  # punctuation has no GUID
                    continue
                if pd.isnull(pos):
                    poses.append("?")
                else:
                    poses.append(pos)
        phrase_data["POS"] = "\t".join(poses)

    phrase_data["Primary_Text"] = compose_surface_string(list(word_cols["surface"]))

    for i, word in morph_cols.iterrows():
        if gloss_key not in word or word[gloss_key] is np.nan:
            log.warning(
                f"No gloss line ({gloss_key}) found for word {''.join(word[obj_key])} "
            )
        fixed_gloss = []
        for gloss, morph_type in zip(word[gloss_key], word.get("morph_type", "?")):
            if morph_type == "suffix" and not gloss.startswith("-"):
                gloss = "-" + gloss
            elif morph_type == "prefix" and not gloss.endswith("-"):
                gloss += "-"
            fixed_gloss.append(gloss)
        ex_df.loc[i][gloss_key] = (
            "-".join(fixed_gloss)
            .replace("--", "-")
            .replace("=-", "=")
            .replace("-=", "=")
        )

    if len(morph_cols) == 0:
        log.warning(f"{ex_id} has no glossing")
        morph_cols[gloss_key] = ""
    else:
        for gloss_col in [obj_key, gloss_key]:
            if gloss_col in morph_cols:
                morph_cols[gloss_col] = morph_cols[gloss_col].apply(
                    lambda x: "-".join(x)
                    .replace("--", "-")
                    .replace("=-", "=")
                    .replace("-=", "=")
                )
            else:
                morph_cols[gloss_col] = ""

    if len(morph_cols) > 0:
        out_dict = {
            "ID": ex_id,
            conf.get("segmented_obj_label", "Primary_Text"): surf_sentence,
            conf.get("segmented_obj_label", "Analyzed_Word"): "\t".join(
                morph_cols[obj_key]
            ),
            conf.get("gloss_label", "Gloss"): "\t".join(morph_cols[gloss_key]),
            "Text_ID": text_id,
        }
    else:
        return None

    # word_ids = [x for x in ex_df.get("@guid", []) if not pd.isnull(x)]
    # word_meanings = [x for x in word_cols.get(word_gloss_key, []) if not pd.isnull(x)]

    word_count = 0
    for word_rec in ex_df.to_dict("records"):
        if not isinstance(word_rec.get(obj_key, None), list):
            if not pd.isnull(word_rec.get("@guid", None)) and verbose is True:
                log.warning("Unglossed word:")
                print(ex_df)
            continue
        word_id = word_rec["@guid"]
        obj = "".join(word_rec[obj_key])
        word_forms.setdefault(
            word_id, {"ID": word_id, "Form": obj, "Meaning": [word_rec[gloss_key]]}
        )
        if word_rec[gloss_key] not in word_forms[word_id]["Meaning"]:
            word_forms[word_id]["Meaning"].append(word_rec[gloss_key])
            sentence_slices.append(
                {
                    "ID": f"{ex_id}-{word_count}",
                    "Example_ID": ex_id,
                    "Form_ID": word_id,
                    "Index": word_count,
                    "Form_Meaning": word_rec[gloss_key],
                }
            )
        if lexicon is not None:
            if word_id not in form_slices:
                form_slices[word_id] = []
                for m_c, (morph_obj, morph_gloss, morph_type) in enumerate(
                    zip(
                        re.split(re.compile("|".join(delimiters)), obj),
                        re.split(re.compile("|".join(delimiters)), word_rec[gloss_key]),
                        word_rec["morph_type"],
                    )
                ):
                    m_id = retrieve_morpheme_id(
                        morph_obj, morph_gloss, lexicon, morph_type
                    )
                    if m_id:
                        form_slices[word_id].append(
                            {
                                "ID": f"{word_id}-{str(m_c)}",
                                "Form_ID": word_id,
                                "Form": word_rec["surface"],
                                "Form_Meaning": word_rec[gloss_key],
                                "Morph_ID": m_id,
                                "Morpheme_Meaning": morph_gloss,
                                "Index": str(m_c),
                            }
                        )
                    else:
                        log.warning(
                            f"No hits for {morph_obj} '{morph_gloss}' in lexicon! ({ex_id})"
                        )
        word_count += 1

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


def convert(flextext_file="", lexicon_file=None, config_file=None, output_dir=None):
    output_dir = output_dir or os.path.dirname(os.path.realpath(flextext_file))
    output_dir = Path(output_dir)
    logging.basicConfig(
        filename=output_dir / f"flex2csv_{os.path.splitext(flextext_file)[0]}.log",
        filemode="w",
        level="INFO",
        format="%(levelname)s::%(name)s::%(message)s",
    )
    if flextext_file == "":
        log.error("No .flextext file provided")
        return None
    if not config_file:
        log.warning("Running without a config file.")
        conf = {}
    else:
        with open(config_file, encoding="utf-8") as f:
            conf = yaml.safe_load(f)

    global lexicon
    global form_slices
    global sentence_slices
    global word_forms

    word_forms = {}
    form_slices = {}
    sentence_slices = []
    if lexicon_file is None:
        log.warning(
            "No lexicon file provided. If you want the output to contain morpheme IDs, provide a csv file with ID, Form, and Meaning."
        )
        lexicon = None
    elif Path(lexicon_file).suffix == ".csv":
        log.info(f"Adding lexicon from CSV file {lexicon_file}")
        lexicon = pd.read_csv(lexicon_file, encoding="utf-8")
        lexicon["Form_Bare"] = lexicon["Form"].apply(
            lambda x: re.sub(re.compile("|".join(delimiters)), "", x)
        )
        for split_col in ["Form_Bare", "Form", "Meaning"]:
            lexicon[split_col] = lexicon[split_col].apply(lambda x: x.split("; "))
    else:
        log.warning(f"{lexicon_file} is not a valid lexicon file format.")
    # name = flextext_file.split("/")[-1].split(".")[0]
    csv_out = output_dir / conf.get("output_file", "sentences.csv")

    conf.setdefault("gloss_lg", "en")
    with open(flextext_file, "r", encoding="utf-8") as f:
        content = f.read()
    example_list = []
    texts = bf.data(fromstring(content))["document"]["interlinear-text"]
    if not isinstance(texts, list):
        texts = [texts]
    texts = to_dict(texts)
    text_metadata = {}
    log.info(f"Parsing {len(texts)} texts")
    for text_count, bs in enumerate(texts):
        metadata = {}
        if "item" not in bs:
            log.error(f"Text #{text_count+1} has no title or language information")
        else:
            if not isinstance(bs["item"], list):
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
                log.info(
                    f"Assuming that the language field [{abbr_lg}] stores title-abbreviation info"
                )
            text_abbr = slugify(metadata["title-abbreviation"][abbr_lg])
        else:
            text_abbr = "missing-text-id"

        text_metadata[text_abbr] = metadata
        if "title" in metadata:
            title_lg = list(metadata["title"].keys())[0]
            if len(metadata["title"].keys()) > 1:
                log.info(f"Assuming that language field [{title_lg}] stores title info")
            title = metadata["title"][title_lg]
        else:
            title = "_MISSING_"

        log.info(f"Parsing text [{text_abbr}] '{title}'")

        examples = listify(bs["paragraphs"]["paragraph"])

        obj_missing = False
        if "obj_lg" not in conf:
            obj_missing = True
        for ex_cnt, example in enumerate(examples):
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
            if obj_missing:
                for item in list(subexamples[0]["words"].values())[0]:
                    for subitem in item["item"]:
                        if "@lang" in subitem and subitem["@lang"] != "en":
                            conf["obj_lg"] = subitem["@lang"]
                            obj_missing = False
            for subex_count, data in enumerate(subexamples):
                example_list.append(
                    extract_flex_record(
                        example=data,
                        text_id=text_abbr,
                        obj_lg=conf["obj_lg"],
                        gloss_lg=conf["gloss_lg"],
                        fallback_exno=str(ex_cnt) + "-" + str(subex_count),
                        column_mappings=conf.get("mappings", {}),
                        drop_columns=conf.get("delete", []),
                        conf=conf,
                        lexicon=lexicon,
                    )
                )
    ex_df = pd.DataFrame.from_dict(example_list)
    ex_df["Language_ID"] = conf.get("Language_ID", conf["obj_lg"])
    ex_df.to_csv(csv_out, index=False)
    word_forms = pd.DataFrame.from_dict(word_forms.values())
    word_forms["Meaning"] = word_forms["Meaning"].apply(lambda x: "; ".join(x))
    word_forms.to_csv(output_dir / "wordforms.csv", index=False)

    final_slices = []
    for slices in form_slices.values():
        for sl in slices:
            final_slices.append(sl)
    if len(final_slices) > 0:
        form_slices = pd.DataFrame.from_dict(final_slices)
        form_slices.to_csv(output_dir / "form_slices.csv", index=False)

    if len(sentence_slices) > 0:
        sentence_slices = pd.DataFrame.from_dict(sentence_slices)
        sentence_slices.to_csv(output_dir / "sentence_slices.csv", index=False)

    text_table = []
    for text_id, data in text_metadata.items():
        tdic = {"ID": text_id}
        for kind, kdic in data.items():
            for lg, value in kdic.items():
                tdic[f"{kind}_{lg}"] = value
        text_table.append(tdic)
    text_table = pd.DataFrame.from_dict(text_table)
    text_table.to_csv(output_dir / "texts.csv", index=False)

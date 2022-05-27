from xml.etree.ElementTree import fromstring
from xmljson import badgerfish as bf
from collections import OrderedDict
import os
import re
import csv
import unicodedata


def convert(filename, language_id):
    dir_path = os.path.dirname(os.path.realpath(filename))
    name = filename.split("/")[-1].split(".")[0]
    cldf_db = dir_path + "/%s_from_flex.csv" % name
    f = open(filename, "r")
    content = f.read().replace("http://www.w3.org/1999/xhtml", "")
    # print(content)
    morphemes = {}
    for entry in bf.data(fromstring(content))["html"]["body"]["div"]:
        meanings = []
        if entry["@class"] == "letHead":
            lang_id = entry["span"]["@lang"]
            continue
        morph_id = entry["@id"].replace("-", "_")
        # print("%s:" % morph_id)
        # print(entry)
        for bs_span in entry["span"]:
            if type(bs_span) != OrderedDict:
                continue
            if bs_span["@class"] == "mainheadword" or bs_span["@class"] == "headword":
                if "a" in bs_span["span"].keys():
                    form = bs_span["span"]["a"]["$"]
                else:
                    form = bs_span["span"]["span"][0]["a"]["$"]
                # print(form)
                # form = form.replace("-","").replace("=","-")
                # print(form)
            elif bs_span["@class"] == "senses":
                # print(bs_span["span"].keys())
                if type(bs_span["span"]) is not list:
                    morpheme_properties = [bs_span["span"]]
                else:
                    morpheme_properties = bs_span["span"]
                for morpheme_property in morpheme_properties:
                    if morpheme_property["@class"] == "sensecontent":
                        if type(morpheme_property["span"]) == list:
                            trans_content = morpheme_property["span"][1]["span"]
                        else:
                            trans_content = morpheme_property["span"]["span"]
                        if type(trans_content) is not list:
                            trans_content = [trans_content]
                        for more_bs in trans_content:
                            if more_bs["@class"] == "definitionorgloss":
                                meanings.append(str(more_bs["span"]["$"]))
                    # in case this is a "variant of"…
                    # print(morpheme_property["span"][0]["span"]["$"])
                    # meaning = morpheme_property["span"][0]["span"]["$"]
                    # if type(morpheme_property["span"]) is list:
        #                     orig_id = morpheme_property["span"][1]["span"]["span"]["a"]["@href"].replace("-","_").replace("#","")
        #                     meaning = "todo"
        #                 else:
        #                     if "@lang" in morpheme_property["span"].keys():
        #                         meaning = morpheme_property["span"]["$"]
        meaning = "; ".join(meanings)
        if meaning != "" and form != "":
            ascii_form = (
                unicodedata.normalize("NFKD", form)
                .encode("ascii", "ignore")
                .decode("ascii")
            )
            my_id = (
                re.sub(r"[^A-Za-z0-9_]+", "", ascii_form)
                .replace(" ", "_")
                .replace("*", "_")
            )
            append = ""
            c = 0
            while my_id + append in morphemes.keys():
                c += 1
                append = str(c)
            morphemes[my_id + append] = {
                "Form": "; ".join([form]),
                "ID": my_id + append,
                "Meaning": "; ".join([str(meaning)]),
                "Language_ID": language_id,
            }
    with open(cldf_db, "w") as csvfile:
        headers = ["ID", "Language_ID", "Form", "Meaning"]
        writer = csv.DictWriter(csvfile, quoting=csv.QUOTE_ALL, fieldnames=headers)
        writer.writeheader()
        for i, m in enumerate(morphemes.values()):
            # print("%s. %s : %s" % (i, m["Form"], m["Meaning"]))
            writer.writerow(m)

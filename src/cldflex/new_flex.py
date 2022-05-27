from lxml import etree as ET
import pandas as pd
import re

meta_lang = "en"
obj_lang = "arn"
lg_id = obj_lang
tree = ET.parse(
    "/Users/florianm/Dropbox/Uni/Research/documentation_project/gramr/mapudungun/mapudungun_texts.flextext"
)
root = tree.getroot()
exs = []

lexicon = pd.read_csv("lex_test.csv")
lexicon["Segments"] = lexicon["Form"].str.replace("-", "").replace("=", "")


def get_match_id(form, meaning):
    meaning = meaning.strip("-").strip("=")
    form = form.replace(".", " ")
    hits = lexicon[(lexicon["Meaning"] == meaning) & (lexicon["Segments"] == form)]
    if len(hits) != 1:
        print(f"No lexicon entries found for {form} '{meaning}'")
        return "X"
    else:
        return hits.iloc[0]["ID"]


for text in root:
    meta_titles = text.findall(f"./item[@type='title'][@lang='{meta_lang}']")  #
    obj_titles = text.findall(f"./item[@type='title'][@lang='{obj_lang}']")  #

    if len(meta_titles) > 0:
        meta_title = meta_titles[0]
    else:
        meta_title = ""

    if len(obj_titles) > 0:
        obj_title = obj_titles[0]
    else:
        obj_title = ""

    meta_abbrevs = text.findall(
        f"./item[@type='title-abbreviation'][@lang='{meta_lang}']"
    )  #
    obj_abbrevs = text.findall(
        f"./item[@type='title-abbreviation'][@lang='{obj_lang}']"
    )  #
    if len(meta_abbrevs) > 0:
        if len(obj_abbrevs) > 0:
            if meta_abbrevs[0].text != obj_abbrevs[0].text:
                print(f"Mismatch between '{meta_lang}' and '{obj_lang}' abbreviations")
            else:
                abbrev = obj_abbrevs[0].text
        abbrev = meta_abbrevs[0].text
    elif len(obj_abbrevs) > 0:
        abbrev = obj_abbrevs[0].text
    else:
        abbrev = "UNKNOWN"

    for paragraphs in text.findall("paragraphs"):
        for par_c, paragraph in enumerate(paragraphs.findall("paragraph")):
            for phrases in paragraph.findall("phrases"):
                for phr_c, phrase in enumerate(phrases.findall("phrase")):
                    translation = phrase.findall("item[@type='gls']")[0].text
                    start, end, speaker = (
                        phrase.get("begin-time-offset"),
                        phrase.get("end-time-offset"),
                        phrase.get("speaker"),
                    )
                    surface_words = []
                    obj_words = []
                    gloss_words = []
                    if phr_c > 0:
                        part = f"{par_c+1}.{phr_c+1}"
                    else:
                        part = f"{par_c+1}"
                    ex_id = f"{abbrev}-{part}"
                    for words in phrase.findall("words"):
                        for word in words.findall("word"):
                            item = word.findall(f"./item")
                            surface_words.append(item[0].text)
                            obj_words.append([])
                            gloss_words.append([])
                            for morphemes in word.findall("morphemes"):
                                for morpheme in morphemes.findall("morph"):
                                    obj = morpheme.findall("item[@type='txt']")
                                    gloss = morpheme.findall("item[@type='gls']")
                                    if (
                                        len(obj) == 0
                                        or len(gloss) == 0
                                        or len(obj) != len(gloss)
                                    ):
                                        print(f"No bueno: {obj} and/or {gloss}")
                                    else:
                                        obj = obj[0].text.replace(" ", ".")
                                        gloss = gloss[0].text
                                        morph_type = "root"
                                        for sep in ["-", "="]:
                                            if obj[0] == sep:
                                                gloss = sep + gloss
                                            elif obj[-1] == sep:
                                                gloss += sep
                                        obj_words[-1].append(obj)
                                        gloss_words[-1].append(gloss)
                                        for obj_material, gloss_material in zip(
                                            obj_words[-1], gloss_words[-1]
                                        ):
                                            # print(obj_material)
                                            # print(gloss_material)
                                            print(
                                                get_match_id(
                                                    obj_material, gloss_material
                                                )
                                            )
                    obj_string = " ".join(["".join(x) for x in obj_words])
                    gloss_string = " ".join(["".join(x) for x in gloss_words])
                    exs.append(
                        {
                            "ID": ex_id,
                            "Language_ID": lg_id,
                            "Surface": " ".join(surface_words),
                            "Form": obj_string,
                            "Gloss": gloss_string,
                            "Translation": translation,
                            "Part": part,
                            "Text_ID": abbrev,
                            "Start": start,
                            "End": end,
                            "Speaker": speaker,
                        }
                    )

df = pd.DataFrame(exs)
df.to_csv("flex_test.csv", index=False)

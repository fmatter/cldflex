import pandas as pd
from lxml import etree as ET

tree = ET.parse(
    "~/Dropbox/Uni/Research/documentation_project/gramr/mapudungun/mapudungun_dic.xml"
)
root = tree.getroot()
prefix = "http://www.w3.org/1999/xhtml"
body = root.findall(f"{{{prefix}}}body")
if len(body) == 0:
    print("No body found")
else:
    body = body[0]
entries = body.findall(f"./{{{prefix}}}div[@class='entry']")
found_entries = []
for entry in entries:
    entry_id = entry.get("id")
    headword = entry.findall(f"./{{{prefix}}}span[@class='mainheadword']")
    form = headword[0][0][0].text
    pos = entry.findall(f"./*//{{{prefix}}}span[@class='partofspeech']")
    if len(pos) > 0:
        pos = pos[0][0].text
    else:
        pos = None
    morphtype = entry.findall(f"./*//{{{prefix}}}span[@class='morphtype']")
    if len(morphtype) > 0:
        morphtype = morphtype[0][0][0].text
    else:
        morphtype = None
    senses = entry.findall(f"./*//{{{prefix}}}span[@class='definitionorgloss']")
    glosses = []
    for sense in senses:
        glosses.append(sense[0].text.replace(" ", "."))
    # print(entry_id)
    # print(form)
    # print(pos)
    # print(morphtype)
    # print(glosses)
    found_entries.append(
        {"ID": entry_id, "Form": form, "POS": pos, "Meaning": "; ".join(glosses)}
    )

df = pd.DataFrame(found_entries)
df.to_csv("lex_test.csv", index=False)

from lxml import etree as ET
import pandas as pd
import re

meta_lang = "en"
obj_lang = "mkt"
lg_id = obj_lang
tree = ET.parse(
    "/Users/florianm/Dropbox/Uni/Research/documentation_project/gramr/vamale_source_data/lift/vamale_dic.lift"
)
root = tree.getroot()
for entry in root.findall("entry"):
    form = entry.findall("lexical-unit/form/text")
    form = form[0]
    # print(form.text)

    traits = entry.findall("trait")
    found_traits = {}
    for trait in traits:
        found_trai(trait.get("name"), trait.get("value"))

# <Element lexical-unit at 0x1138d6cd0>
# <Element trait at 0x1138d6d20>
# <Element citation at 0x1138d6d70>
# <Element relation at 0x1138d6d20>
# <Element sense at 0x1138d6cd0>

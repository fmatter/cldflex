import os
import string
import script_converter

punctuation = "!@#$%^&*()_+<>?:.,;"


def objectify(input, mapping_file=None):
    for c in input:
        if c in punctuation:
            input = input.replace(c, "")
    if mapping_file:
        input = script_converter.convert(input, mapping_file)
    return input


def convert(filename, mapping_file=None):
    print(f"Processing {filename}…")
    dir_path = os.path.dirname(os.path.realpath(filename))
    name = os.path.splitext(filename)[0]
    flex_out = dir_path + "/%s_flexified.flextext" % name
    file_content = open(filename, "r").read()
    preamble, content = file_content.split("\n\n\n")
    info = {"id": name}
    for entry in preamble.split("\n"):
        tag, info_tent = entry.split(": ", 1)
        info[tag] = info_tent
    print(
        f"""id: {info['id']}
title: {info['title']}
source: {info['src']}"""
    )
    name = info["id"]
    entries = []

    line_map = {0: "surf", 1: "trans", 2: "p", 3: "o_trans"}

    ex_cnt = 0
    for i, part in enumerate(content.split("\n\n")):
        ex_cnt += 1
        lines = part.split("\n")
        entries.append({})
        for j, line in enumerate(lines):
            entries[-1][line_map[j]] = line
        entries[-1]["obj"] = objectify(lines[0], mapping_file=mapping_file)

    # output = []
    # for entry in entries:
    #     output.append(entry["obj"])
    # output = "\n".join(output)
    output = f"""<?xml version="1.0" encoding="utf-8"?>
<document version="2">
  <interlinear-text guid="e4e1a825-4260-43bd-b7ca-178a3e5c3a17">"""

    output += f"""
    <item type="title" lang="{info['lg_id']}">{info['title']}</item>
    <item type="title" lang="en">{info['title_en']}</item>
    <item type="title-abbreviation" lang="{info['lg_id']}">{name}</item>
    <item type="title-abbreviation" lang="en">{name}</item>
    <item type="source" lang="{info['lg_id']}">{info['src']}</item>"""

    output += """
    <paragraphs>"""

    for i, entry in enumerate(entries):
        output += f"""
        <paragraph guid="341a7f9f-ea59-4b4d-aee4-f397e12def8e">
            <phrases>
              <phrase guid="674114d7-6707-42e1-af99-16b5d7079777">
                <item type="segnum" lang="en">{i+1}</item>
                <words>
                """

        words = entry["obj"].split(" ")
        for word in words:
            output += f"""<word guid="ff7608dd-6e53-458c-9ee3-3ea3a1591963">
                    <item type="txt" lang="{info['lg_id']}">{word}</item>
                  </word>
                  """
        output += f"""</words>
                <item type="note" lang="en">{entry['p']}</item>
                 <item type="gls" lang="en">{entry['trans']}</item>
               </phrase>
            </phrases>
           </paragraph>"""
    output += f"""
           </paragraphs>
           <languages>
             <language lang="en" font="Charis SIL" />
             <language lang="{info['lg_id']}" font="Charis SIL" vernacular="true" />
           </languages>
        </interlinear-text>
    </document>"""

    file = open(flex_out, "w+")
    file.write(output)

    print(f"parts: {ex_cnt}\nexported to: {flex_out}")

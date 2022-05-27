import os
import sys

dir_path = os.path.dirname(os.path.realpath(sys.argv[1]))
name = sys.argv[1].split("/")[-1].split(".")[0]
flex_out = dir_path + "/%s_flexified.xml" % name
lang = sys.argv[2]
entries = []
content = open(sys.argv[1], "r").read().split("\n")
for i in content:
    entries.append([i.split("\t")[0], i.split("\t")[1]])
output = """<?xml version="1.0" encoding="utf-8"?>
<document version="2">
  <interlinear-text guid="c6511db3-2c2b-4199-ad20-5922a05c71a2">
    <paragraphs>"""
for entry in entries:
    output += """<paragraph guid="341a7f9f-ea59-4b4d-aee4-f397e12def8e">
        <phrases>
          <phrase guid="674114d7-6707-42e1-af99-16b5d7079777">
            <item type="segnum" lang="en">1</item>
            <words>"""
    words = entry[0].split(" ")
    for word in words:
        output += """<word guid="ff7608dd-6e53-458c-9ee3-3ea3a1591963">
                <item type="txt" lang="%s">%s</item>
              </word>""" % (
            lang,
            word,
        )
    output += (
        """</words>
            <item type="gls" lang="en">%s</item>
          </phrase>
        </phrases>
      </paragraph>"""
        % entry[1]
    )
output += (
    """</paragraphs>
    <languages>
      <language lang="en" font="Charis SIL" />
      <language lang="%s" font="Charis SIL" vernacular="true" />
    </languages>
  </interlinear-text>
</document>"""
    % lang
)
file = open(flex_out, "w+")
file.write(output)

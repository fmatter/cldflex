# import sys
# import os
# import csv

# dir_path = os.path.dirname(os.path.realpath(sys.argv[1]))
# cldf_db = dir_path + "/cldf_examples.csv"
# tier_names = {
#     "ts-LCZ": {
#         "surf": "ts-LCZ",
#         "trans": "tl-LCZ",
#         "obj": "morph-P1-LCZ",
#         "gloss": "gloss-P1-LCZ",
#     },
#     "ts-MM": {
#         "surf": "ts-MM",
#         "trans": "tl-MM",
#         "obj": "morph-P2-MM",
#         "gloss": "gloss-P2-MM",
#     },
# }


# def extractFromELAN(example, counter, speaker):
#     return {
#         "Example_ID": counter,
#         "Sentence": entry[tier_names[speaker]["surf"]],
#         "Segmentation": entry[tier_names[speaker]["obj"]],
#         "Gloss": entry[tier_names[speaker]["gloss"]],
#         "Translation": entry[tier_names[speaker]["trans"]],
#         "Notes": "TODO COPY NOTES HERE",
#         "Speaker": speaker.split("-")[1],
#     }


# with open(sys.argv[1]) as f:
#     reader = csv.DictReader(f, delimiter="\t")
#     data = [r for r in reader]
# counter = 0

# example_list = []
# for entry in data:
#     counter += 1
#     for speaker, tier in tier_names.items():
#         if entry[speaker] != "":
#             example_list.append(extractFromELAN(entry, counter, speaker))
# with open(cldf_db, "w") as csvfile:
#     headers = [
#         "Example_ID",
#         "Sentence",
#         "Segmentation",
#         "Gloss",
#         "Translation",
#         "Speaker",
#         "Notes",
#     ]
#     writer = csv.DictWriter(csvfile, quoting=csv.QUOTE_ALL, fieldnames=headers)
#     writer.writeheader()
#     for example in example_list:
#         writer.writerow(example)

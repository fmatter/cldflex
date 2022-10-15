import configparser
from datetime import datetime
from jinja2 import Template

config = configparser.ConfigParser()
config.read(".bumpversion.cfg")
now = datetime.now()
metadata = {
    "version": config["bumpversion"]["current_version"],
    "date": now.strftime("%Y-%m-%d"),
}
template = open("etc/CITATION.cff", "r", encoding="utf-8").read()
j2_template = Template(template)

with open("CITATION.cff", "w", encoding="utf-8") as f:
    f.write(j2_template.render(metadata))

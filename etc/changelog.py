import keepachangelog
import configparser

config = configparser.ConfigParser()
config.read(".bumpversion.cfg")

changes = keepachangelog.release(
    "CHANGELOG.md", new_version=config["bumpversion"]["current_version"]
)

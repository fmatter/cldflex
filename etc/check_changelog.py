import keepachangelog
import webbrowser

changes = keepachangelog.to_dict("CHANGELOG.md", show_unreleased=True)
webbrowser.open(changes["unreleased"]["url"], new=2)

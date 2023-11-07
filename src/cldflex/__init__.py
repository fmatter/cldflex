"""Top-level package for cldflex."""
import logging

import colorlog

handler = colorlog.StreamHandler(None)
handler.setFormatter(
    colorlog.ColoredFormatter("%(log_color)s%(levelname)-7s%(reset)s %(message)s")
)
log = logging.getLogger(__name__)
log.setLevel(logging.INFO)
log.propagate = True
log.addHandler(handler)


SEPARATOR = "; "

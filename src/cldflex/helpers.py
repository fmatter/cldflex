import logging
from slugify import slugify


log = logging.getLogger(__name__)


def listify(item):
    if not isinstance(item, list):
        return [item]
    return item


def retrieve_morpheme_id(o, g, lex, morph_type):
    candidates = lex[
        (lex["Form_Bare"].apply(lambda x: o in x))
        & (lex["Meaning"].apply(lambda x: g in x))
    ]
    if len(candidates) == 1:
        return candidates.iloc[0]["ID"]
    if len(candidates) == 0:
        return None
    if len(candidates) > 0:
        narrow_candidates = candidates[candidates["Type"] == morph_type]
        if len(narrow_candidates) == 1:
            return narrow_candidates.iloc[0]["ID"]
        log.warning(f"Multiple lexicon entries for {o} '{g}', using the first result:")
        print(morph_type)
        print(candidates)
        return candidates.iloc[0]["ID"]
    return None


def get_slug(meaning, meanings):
    slug_count = 0
    while slugify(meaning) + "-" + str(slug_count) in meanings:
        slug_count += 1
    return slugify(meaning) + "-" + str(slug_count)

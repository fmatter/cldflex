import logging
from slugify import slugify


log = logging.getLogger(__name__)


def retrieve_morpheme_id(o, g, lex, morph_type):
    g = g.strip("=")
    candidates = lex[
        (lex["Form_Bare"].apply(lambda x: o in x))
        & (lex["Meaning"].apply(lambda x: g in x))
    ]
    if len(candidates) == 1:
        return (
            candidates.iloc[0]["ID"],
            candidates.iloc[0]["Parameter_ID"][candidates.iloc[0]["Meaning"].index(g)],
        )
    if len(candidates) > 0:
        narrow_candidates = candidates[candidates["Type"] == morph_type]
        if len(narrow_candidates) == 1:
            return (
                narrow_candidates.iloc[0]["ID"],
                narrow_candidates.iloc[0]["Parameter_ID"][
                    narrow_candidates.iloc[0]["Meaning"].index(g)
                ],
            )
        log.warning(f"Multiple lexicon entries for {o} '{g}', using the first hit:")
        print(morph_type)
        print(candidates)
        return (
            candidates.iloc[0]["ID"],
            candidates.iloc[0]["Parameter_ID"][candidates.iloc[0]["Meaning"].index(g)],
        )
    return None, None


empty_slugs = {}


def slug(string):
    if slugify(string) != "":
        return slugify(string)
    if string in empty_slugs:
        return empty_slugs[string]
    c = 0
    test_string = f"null-{c}"
    while test_string in empty_slugs.values():
        c += 1
        test_string = f"null-{c}"
    empty_slugs[string] = test_string
    return test_string
